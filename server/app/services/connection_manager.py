"""ConnectionManager — in-process WebSocket connection registry.

Tracks which WebSocket connections belong to each room so that messages
published via Redis pub/sub can be forwarded to the correct connections
on *this* ECS task.  Cross-task fan-out is handled by Redis pub/sub;
this class only deals with connections local to the current process.

Thread-safety: FastAPI/Starlette runs in a single asyncio event loop, so
no locking is required.  All methods must be called from that loop.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

_logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registry of active WebSocket connections grouped by room ID.

    Each room maps to a list of ``(player_id, WebSocket)`` pairs.  A player
    may have at most one active connection per room at any time; older
    connections are replaced on reconnect via :meth:`disconnect` followed
    by :meth:`register`.
    """

    def __init__(self) -> None:
        self._rooms: dict[str, list[tuple[str, WebSocket]]] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def register(
        self,
        room_id: str,
        player_id: str,
        websocket: WebSocket,
    ) -> None:
        """Register an already-accepted WebSocket connection for a player.

        The route handler calls ``await websocket.accept()`` before calling
        this method.  We intentionally do not accept here so that the auth
        check can happen before registration.
        """
        if room_id not in self._rooms:
            self._rooms[room_id] = []
        self._rooms[room_id].append((player_id, websocket))
        _logger.info("Player %s registered in room %s", player_id, room_id)

    def deregister(
        self,
        room_id: str,
        player_id: str,
        websocket: WebSocket,
    ) -> None:
        """Remove a specific WebSocket connection from the registry.

        Identified by *websocket* identity (``is``) rather than player_id
        to handle edge cases where a player has two racing connections.
        """
        if room_id not in self._rooms:
            return
        self._rooms[room_id] = [
            (pid, ws)
            for pid, ws in self._rooms[room_id]
            if ws is not websocket
        ]
        if not self._rooms[room_id]:
            del self._rooms[room_id]
        _logger.info("Player %s deregistered from room %s", player_id, room_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_player_ids(self, room_id: str) -> list[str]:
        """Return the list of player IDs currently connected in a room."""
        return [pid for pid, _ in self._rooms.get(room_id, [])]

    def connection_count(self, room_id: str) -> int:
        """Return the number of active connections in a room."""
        return len(self._rooms.get(room_id, []))

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send_to_player(
        self,
        room_id: str,
        player_id: str,
        message: dict[str, Any],
    ) -> None:
        """Send *message* to a specific player in a room.

        If the player has no active connection (e.g. mid-reconnect) the
        call is silently ignored.  Any send error is logged but not raised.
        """
        for pid, ws in self._rooms.get(room_id, []):
            if pid == player_id:
                try:
                    await ws.send_json(message)
                except Exception:
                    _logger.exception(
                        "Failed to send to player %s in room %s",
                        player_id,
                        room_id,
                    )

    async def broadcast_to_room(
        self,
        room_id: str,
        message: dict[str, Any],
    ) -> None:
        """Broadcast *message* to every connection in a room concurrently.

        Failed sends are logged individually but do not prevent other
        connections from receiving the message.
        """
        connections = list(self._rooms.get(room_id, []))
        if not connections:
            return

        results = await asyncio.gather(
            *[ws.send_json(message) for _, ws in connections],
            return_exceptions=True,
        )
        for (pid, _), result in zip(connections, results):
            if isinstance(result, Exception):
                _logger.warning(
                    "Broadcast failed for player %s in room %s: %s",
                    pid,
                    room_id,
                    result,
                )


# ---------------------------------------------------------------------------
# Module-level singleton — shared across all WS handlers in this process.
# ---------------------------------------------------------------------------
manager = ConnectionManager()
