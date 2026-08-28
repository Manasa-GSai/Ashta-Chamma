"""Room service: business logic for room lifecycle management.

Responsibilities: room code generation, player join/leave, AI seat filling,
activity tracking, and audit logging.  All DB/Redis I/O is delegated to
the repository layer and the injected redis client.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime
from typing import Any

from app.core.config import settings
from app.models.room import AuditLog, Room, RoomPlayer, RoomStatus
from app.repositories.room_repository import RoomRepository
from app.schemas.room import (
    CreateRoomRequest,
    CreateRoomResponse,
    JoinResponse,
    PlayerInfo,
    RoomResponse,
)


# ---------------------------------------------------------------------------
# Domain exceptions
# ---------------------------------------------------------------------------


class RoomNotFoundError(Exception):
    """Raised when a room code resolves to no DB record."""


class RoomFullError(Exception):
    """Raised when trying to join a room at capacity."""


class RoomAlreadyStartedError(Exception):
    """Raised when a mutating action is attempted on a non-waiting room."""


class PlayerNotInRoomError(Exception):
    """Raised when a leave request comes from a non-member."""


class AiPersonaNotFoundError(Exception):
    """Raised when a requested AI persona ID does not exist or is inactive."""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


def _generate_room_code() -> str:
    """Return a 6-character uppercase hexadecimal room code.

    Uses ``secrets.token_hex(3)`` which produces 3 random bytes encoded as
    6 hex characters (0–9, A–F) — alphanumeric and case-insensitive.
    """
    return secrets.token_hex(3).upper()


class RoomService:
    """Handles all room lifecycle operations."""

    def __init__(self, repo: RoomRepository, redis: Any = None) -> None:
        self._repo = repo
        # Redis is optional; if absent, activity tracking silently degrades
        self._redis = redis

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_room(
        self,
        request: CreateRoomRequest,
        host_user_id: uuid.UUID,
        host_clerk_id: str,
        host_display_name: str,
    ) -> CreateRoomResponse:
        """Create a new room, add the host and any requested AI players.

        Returns the minimal ``{room_id, code}`` payload expected by the
        POST /api/rooms endpoint.
        """
        num_ai = len(request.ai_persona_ids)
        # Host always occupies one seat, so AI count must not fill all seats
        if num_ai >= request.max_players:
            raise ValueError(
                "ai_persona_ids has too many entries: must leave at least 1 seat for the host"
            )

        # Validate all requested AI personas up-front before touching the DB
        ai_personas = []
        for persona_id in request.ai_persona_ids:
            persona = await self._repo.get_ai_persona(persona_id)
            if persona is None:
                raise AiPersonaNotFoundError(
                    f"AI persona with id={persona_id} not found or is inactive"
                )
            ai_personas.append(persona)

        code = await self._generate_unique_code()

        room = Room(
            id=uuid.uuid4(),
            code=code,
            host_user_id=host_user_id,
            status=RoomStatus.waiting,
            max_players=request.max_players,
            created_at=datetime.utcnow(),
        )
        await self._repo.create_room(room)

        # Host is always player_index 0 with the first colour
        host_player = RoomPlayer(
            room_id=room.id,
            user_id=host_user_id,
            ai_persona_id=None,
            player_index=0,
            color=settings.player_colors[0],
            joined_at=datetime.utcnow(),
        )
        await self._repo.add_room_player(host_player)

        # AI players fill subsequent indices
        for i, persona in enumerate(ai_personas):
            ai_player = RoomPlayer(
                room_id=room.id,
                user_id=None,
                ai_persona_id=persona.id,
                player_index=i + 1,
                color=settings.player_colors[i + 1],
                joined_at=datetime.utcnow(),
            )
            await self._repo.add_room_player(ai_player)

        await self._repo.create_audit_log(
            AuditLog(
                actor_id=host_clerk_id,
                action="room.created",
                entity_type="room",
                entity_id=str(room.id),
                metadata_={"code": code, "max_players": request.max_players},
                created_at=datetime.utcnow(),
            )
        )

        await self._repo.commit()
        await self._update_redis_activity(str(room.id))

        return CreateRoomResponse(room_id=room.id, code=code)

    async def get_room(
        self,
        code: str,
        requesting_user_id: uuid.UUID,
    ) -> RoomResponse:
        """Return full room details.  Only room members may call this (authz check)."""
        room = await self._repo.get_room_by_code(code)
        if room is None:
            raise RoomNotFoundError(f"Room '{code}' not found")

        # Authorization: only members can read room details
        member_ids = {p.user_id for p in room.players if p.user_id is not None}
        if requesting_user_id not in member_ids:
            raise PermissionError("You are not a member of this room")

        return self._build_room_response(room)

    async def join_room(
        self,
        code: str,
        user_id: uuid.UUID,
        clerk_id: str,
        display_name: str,
    ) -> JoinResponse:
        """Add the authenticated user to the room.

        Idempotent: if the user is already in the room their current slot is
        returned without creating a duplicate entry.
        """
        room = await self._repo.get_room_by_code(code)
        if room is None:
            raise RoomNotFoundError(f"Room '{code}' not found")

        if room.status != RoomStatus.waiting:
            raise RoomAlreadyStartedError("Room has already started or is closed")

        # Idempotency: return existing slot if already joined
        for player in room.players:
            if player.user_id == user_id:
                return JoinResponse(player_index=player.player_index, color=player.color)

        occupied_count = len(room.players)
        if occupied_count >= room.max_players:
            raise RoomFullError("Room is full")

        # Assign the lowest available player index to keep indices compact
        used_indices = {p.player_index for p in room.players}
        next_index = next(i for i in range(room.max_players) if i not in used_indices)
        color = settings.player_colors[next_index]

        new_player = RoomPlayer(
            room_id=room.id,
            user_id=user_id,
            ai_persona_id=None,
            player_index=next_index,
            color=color,
            joined_at=datetime.utcnow(),
        )
        await self._repo.add_room_player(new_player)

        await self._repo.create_audit_log(
            AuditLog(
                actor_id=clerk_id,
                action="room.joined",
                entity_type="room",
                entity_id=str(room.id),
                metadata_={"code": code, "player_index": next_index},
                created_at=datetime.utcnow(),
            )
        )

        await self._repo.commit()
        await self._update_redis_activity(str(room.id))

        return JoinResponse(player_index=next_index, color=color)

    async def leave_room(
        self,
        code: str,
        user_id: uuid.UUID,
        clerk_id: str,
    ) -> None:
        """Remove the authenticated user from the room.

        If the departing user is the host and other human players remain, the
        first remaining human is promoted to host.  If no humans remain, the
        room is marked abandoned.
        """
        room = await self._repo.get_room_by_code(code)
        if room is None:
            raise RoomNotFoundError(f"Room '{code}' not found")

        leaving_player = next(
            (p for p in room.players if p.user_id == user_id), None
        )
        if leaving_player is None:
            raise PlayerNotInRoomError("You are not a member of this room")

        await self._repo.remove_room_player(room.id, user_id)

        # Host reassignment / room closure when host departs
        if room.host_user_id == user_id:
            other_humans = [
                p
                for p in room.players
                if p.user_id is not None and p.user_id != user_id
            ]
            if other_humans:
                # Promote the first remaining human to host
                room.host_user_id = other_humans[0].user_id  # type: ignore[assignment]
            else:
                # No humans left — abandon the room
                room.status = RoomStatus.abandoned

        await self._repo.create_audit_log(
            AuditLog(
                actor_id=clerk_id,
                action="room.left",
                entity_type="room",
                entity_id=str(room.id),
                metadata_={"code": code},
                created_at=datetime.utcnow(),
            )
        )

        await self._repo.commit()
        await self._update_redis_activity(str(room.id))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _generate_unique_code(self) -> str:
        """Generate a room code that does not already exist in the DB."""
        for _ in range(settings.room_code_max_attempts):
            code = _generate_room_code()
            if not await self._repo.code_exists(code):
                return code
        raise RuntimeError(
            f"Failed to generate unique room code after {settings.room_code_max_attempts} attempts"
        )

    async def _update_redis_activity(self, room_id: str) -> None:
        """Record the current timestamp as the room's last activity in Redis.

        Non-fatal: if Redis is unavailable the room expiry check falls back to
        DB-based timestamps (future improvement).
        """
        if self._redis is None:
            return
        try:
            await self._redis.set(
                f"room:{room_id}:last_activity",
                str(time.time()),
                ex=3600,  # hard TTL of 1 hour as a safety net
            )
        except Exception:
            # Redis write failure is non-fatal — log in production
            pass

    def _build_room_response(self, room: Room) -> RoomResponse:
        """Assemble a RoomResponse from a fully eager-loaded Room ORM object."""
        players: list[PlayerInfo] = []
        for p in room.players:
            if p.user_id is not None:
                name = p.user.display_name if p.user else "Unknown"
                is_ai = False
            else:
                name = p.ai_persona.name if p.ai_persona else "AI"
                is_ai = True
            players.append(
                PlayerInfo(
                    player_index=p.player_index,
                    color=p.color,
                    display_name=name,
                    is_ai=is_ai,
                )
            )

        occupied = len(room.players)
        host_name = room.host.display_name if room.host else "Unknown"

        return RoomResponse(
            room_id=room.id,
            code=room.code,
            status=room.status.value,
            host_display_name=host_name,
            max_players=room.max_players,
            players=players,
            available_seats=room.max_players - occupied,
            created_at=room.created_at,
        )
