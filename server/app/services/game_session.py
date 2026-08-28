"""Game session service — Redis-backed interface to the game state machine.

This module is the boundary between the WebSocket handler (WO-016) and the
full GameStateMachine (WO-013 / WO-015).  It encapsulates Redis key layout
and provides the roll/select_pawn/get_state API consumed by the WS handler.

All game state is persisted under ``room:{room_id}:state`` (JSON hash) so
that multiple ECS tasks share the same authoritative view through Redis.

Cowrie roll rules (from legacy game.py):
  0 face-up → 8 (Ashta, extra turn)
  1 face-up → 1 (extra turn)
  2 face-up → 2
  3 face-up → 3
  4 face-up → 4 (Chamma, extra turn)
"""

from __future__ import annotations

import json
import logging
import secrets
from typing import Any

from redis.asyncio import Redis

_logger = logging.getLogger(__name__)

# faces-up count → roll value
_COWRIE_VALUE_TABLE: dict[int, int] = {0: 8, 1: 1, 2: 2, 3: 3, 4: 4}


class GameSession:
    """Service for executing game actions within a single room.

    Instances are stateless — all mutable state lives in Redis — so it is
    safe to create one per WebSocket connection without coordination concerns.
    """

    def __init__(self, room_id: str, redis: Redis) -> None:  # type: ignore[type-arg]
        self._room_id = room_id
        self._redis = redis

    # ------------------------------------------------------------------
    # Redis key helpers
    # ------------------------------------------------------------------

    @property
    def _state_key(self) -> str:
        return f"room:{self._room_id}:state"

    @property
    def _current_player_key(self) -> str:
        return f"room:{self._room_id}:current_player"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_current_player(self) -> str | None:
        """Return the ``player_id`` whose turn it is, or ``None`` if unset."""
        value: str | None = await self._redis.get(self._current_player_key)
        return value

    async def get_state(self) -> dict[str, Any]:
        """Return the full current game state dict stored in Redis."""
        raw: str | None = await self._redis.get(self._state_key)
        if raw:
            return json.loads(raw)  # type: ignore[no-any-return]
        return {}

    async def roll(self, player_id: str) -> dict[str, Any]:
        """Generate a cryptographically fair cowrie roll for *player_id*.

        Uses ``secrets.SystemRandom`` for fairness (anti-cheat requirement).
        Stores the roll result in game state and advances phase to
        ``"selecting"`` so the client can present legal moves.

        Returns a dict with ``value`` (int), ``shells`` (list[bool]),
        and ``player_id`` (str).
        """
        shells: list[bool] = [secrets.randbelow(2) == 1 for _ in range(4)]
        faces_up: int = sum(1 for s in shells if s)
        value: int = _COWRIE_VALUE_TABLE[faces_up]

        state = await self.get_state()
        state["last_roll"] = {
            "value": value,
            "shells": shells,
            "player_id": player_id,
        }
        state["phase"] = "selecting"
        await self._redis.set(self._state_key, json.dumps(state))

        _logger.debug(
            "Roll for player=%s room=%s: value=%d shells=%s",
            player_id,
            self._room_id,
            value,
            shells,
        )
        return {"value": value, "shells": shells, "player_id": player_id}

    async def select_pawn(self, player_id: str, pawn_id: int) -> dict[str, Any]:
        """Record a pawn selection and return the incremental state delta.

        Full move validation (captures, safe squares, home stretch) is
        implemented in WO-013 MoveValidator and will be called here once
        that module is available.  This stub records the action and advances
        phase back to ``"rolling"`` for the next player.

        Returns a dict containing only the changed fields (state delta) so
        clients can apply a minimal reconciliation.
        """
        state = await self.get_state()
        state.setdefault("moves", []).append(
            {"player_id": player_id, "pawn_id": pawn_id}
        )
        state["phase"] = "rolling"
        await self._redis.set(self._state_key, json.dumps(state))

        delta: dict[str, Any] = {
            "last_move": {"player_id": player_id, "pawn_id": pawn_id},
            "phase": "rolling",
        }
        _logger.debug(
            "Pawn selected: player=%s pawn=%d room=%s",
            player_id,
            pawn_id,
            self._room_id,
        )
        return delta
