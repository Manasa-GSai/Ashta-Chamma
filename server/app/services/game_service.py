"""Game service — game start flow and session initialisation.

Bridges room management (PostgreSQL) with the game state machine (Redis).
The host triggers start_game; the service validates preconditions, creates
a GameSession, persists it to Redis, and updates the room record in
PostgreSQL before returning the initial state snapshot for broadcasting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.game.board import PLAYER_COLORS
from app.game.session import GameSession, GameState, PlayerInfo
from app.models.enums import RoomStatus
from app.models.tables import RoomPlayer
from app.providers.redis_provider import RedisProtocol
from app.repositories.room_repository import RoomRepositoryProtocol


class GameStartError(Exception):
    """Raised when a game-start request violates a business rule.

    *http_status* carries the appropriate HTTP status code so the route
    handler can translate this directly to an HTTPException without extra
    mapping logic.
    """

    def __init__(self, message: str, http_status: int = 400) -> None:
        super().__init__(message)
        self.http_status = http_status


class GameService:
    """Orchestrates game start: room validation → session init → persistence."""

    # Redis TTL for game sessions (24 hours is long enough for any game).
    _SESSION_TTL_SECONDS: int = 86_400

    def __init__(
        self,
        room_repo: RoomRepositoryProtocol,
        redis: RedisProtocol,
    ) -> None:
        self._room_repo = room_repo
        self._redis = redis

    async def start_game(
        self,
        room_code: str,
        requester_id: str,
    ) -> dict[str, Any]:
        """Start a game session for the given room.

        Args:
            room_code: Six-character room code.
            requester_id: Clerk user ID of the requesting player.

        Returns:
            Initial game state snapshot suitable for broadcasting.

        Raises:
            GameStartError(404): Room not found.
            GameStartError(403): Requester is not the room host.
            GameStartError(409): Game is already in progress.
            GameStartError(400): Fewer than 2 players in the room.
        """
        room = await self._room_repo.get_room_by_code(room_code)
        if room is None:
            raise GameStartError(f"Room '{room_code}' not found.", http_status=404)

        # Only the room host may start.
        if str(room.host_user_id) != requester_id:
            raise GameStartError(
                "Only the room host can start the game.",
                http_status=403,
            )

        # Starting an already-in-progress game is an error, not silently
        # idempotent, so callers know the request was a no-op.
        if room.status == RoomStatus.PLAYING.value:
            raise GameStartError(
                "The game is already in progress.",
                http_status=409,
            )

        players = await self._room_repo.get_room_players(room.id)
        player_count = len(players)

        if player_count < 2:
            raise GameStartError(
                f"At least 2 players are required to start. Found {player_count}.",
                http_status=400,
            )

        # Build typed player list sorted by player_index for turn order.
        player_infos = self._build_player_infos(players)

        # Construct and initialise the GameSession (pawns placed at home).
        session = GameSession(
            room_id=str(room.id),
            players=player_infos,
        )
        # Ensure deterministic starting state.
        session.state = GameState.ROLLING
        session.current_player_index = 0

        # Persist to Redis — keyed by room UUID for O(1) access during play.
        redis_key = f"room:{room.id}:state"
        await self._redis.set(redis_key, session.to_json(), ex=self._SESSION_TTL_SECONDS)

        # Update room lifecycle state in PostgreSQL.
        now = datetime.now(timezone.utc)
        await self._room_repo.update_room_started(room.id, now)

        # Immutable audit trail: who started the game and when.
        await self._room_repo.create_audit_log(
            actor_id=requester_id,
            action="game.started",
            entity_type="room",
            entity_id=str(room.id),
            metadata={
                "room_code": room_code,
                "player_count": player_count,
                "player_indices": [p.player_index for p in player_infos],
            },
        )

        return session.to_dict()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_player_infos(players: list[RoomPlayer]) -> list[PlayerInfo]:
        """Convert RoomPlayer rows to PlayerInfo objects.

        Rows are sorted by player_index to guarantee consistent turn order.
        The color stored on the row is preferred; if absent (should not
        happen), the canonical color for that index is used as a fallback.
        """
        sorted_players = sorted(players, key=lambda p: p.player_index)
        result: list[PlayerInfo] = []
        for rp in sorted_players:
            fallback_color = PLAYER_COLORS[rp.player_index % len(PLAYER_COLORS)]
            color = rp.color if rp.color else fallback_color
            result.append(
                PlayerInfo(
                    player_index=rp.player_index,
                    color=color,
                    user_id=str(rp.user_id) if rp.user_id else None,
                    ai_persona_id=rp.ai_persona_id,
                    display_name="",
                    is_ai=rp.ai_persona_id is not None,
                )
            )
        return result
