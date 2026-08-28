"""WebSocket route handler for in-game real-time communication.

Every game action (roll, move, chat) MUST update the room's ``last_activity``
key in Redis (``room:{room_id}:last_activity``).  This timestamp is the signal
used by the idle-cleanup task (``app.tasks.cleanup``) to detect abandoned rooms
per BR-5.

Connection registry
-------------------
Active WebSocket connections are tracked in the module-level
``_room_connections`` dict so the cleanup task can reach all clients when a
room is abandoned.  The dict maps ``room_id -> {connection_id -> WebSocket}``.
"""

from __future__ import annotations

import json
import time
import uuid
from collections import defaultdict
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.redis_client import get_redis

router = APIRouter()

# ---------------------------------------------------------------------------
# In-process WebSocket connection registry
# ---------------------------------------------------------------------------

#: Maps room_id → {connection_id → WebSocket}
_room_connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)

# Message types that constitute "game activity" and reset the idle timer.
_GAME_ACTIONS: frozenset[str] = frozenset({"roll_request", "select_pawn", "chat"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _activity_key(room_id: str) -> str:
    """Return the Redis key that stores a room's last-activity Unix timestamp."""
    return f"room:{room_id}:last_activity"


async def _update_last_activity(redis_client: aioredis.Redis, room_id: str) -> None:  # type: ignore[type-arg]
    """Write the current Unix timestamp as the room's last_activity in Redis.

    Called on every game action so the idle-cleanup task has an up-to-date
    signal.  Errors are propagated to the caller, which is responsible for
    deciding whether to treat them as fatal.
    """
    await redis_client.set(_activity_key(room_id), str(int(time.time())))


async def broadcast_to_room(room_id: str, message: dict[str, Any]) -> None:
    """Send a JSON-encoded message to every active WebSocket connection in a room.

    Exceptions from individual sends are swallowed — a stale connection must
    not prevent other clients from receiving the message.
    """
    payload = json.dumps(message)
    for websocket in list(_room_connections[room_id].values()):
        try:
            await websocket.send_text(payload)
        except Exception:  # noqa: BLE001
            # Stale or closed connection — the cleanup task / disconnect handler
            # will remove it from the registry.
            pass


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/rooms/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: str) -> None:
    """Handle a single player's WebSocket session for a game room.

    The client must supply a valid JWT as the ``token`` query parameter.
    Full JWT validation is implemented in the auth middleware (WO-004); for
    now the connection is accepted unconditionally so dependent work orders
    can build on top of this handler.

    Lifecycle
    ---------
    1. Accept the connection and register it in ``_room_connections``.
    2. Record the initial last_activity timestamp in Redis so the room isn't
       immediately flagged as idle.
    3. Dispatch incoming messages to their respective handlers.
    4. On disconnect (normal or error), deregister the connection.
    """
    await websocket.accept()

    # Each connection gets a unique ID so multiple tabs / reconnects are safe.
    connection_id = str(uuid.uuid4())
    _room_connections[room_id][connection_id] = websocket

    redis_client = get_redis()

    # Record initial activity so a freshly joined room is not immediately idle.
    try:
        await _update_last_activity(redis_client, room_id)
    except Exception:  # noqa: BLE001
        pass  # Non-fatal; continue even if Redis is temporarily unavailable

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "code": "INVALID_JSON",
                            "message": "Malformed JSON payload",
                        }
                    )
                )
                continue

            msg_type: str = message.get("type", "")

            # Refresh the idle timer on every recognised game action.
            if msg_type in _GAME_ACTIONS:
                try:
                    await _update_last_activity(redis_client, room_id)
                except Exception:  # noqa: BLE001
                    # Redis unavailability must not crash the handler.
                    pass

            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
            elif msg_type == "roll_request":
                await _handle_roll_request(websocket, room_id, message, redis_client)
            elif msg_type == "select_pawn":
                await _handle_select_pawn(websocket, room_id, message, redis_client)
            elif msg_type == "chat":
                await _handle_chat(websocket, room_id, message, redis_client)
            else:
                await websocket.send_text(
                    json.dumps(
                        {
                            "type": "error",
                            "code": "UNKNOWN_TYPE",
                            "message": f"Unknown message type: {msg_type!r}",
                        }
                    )
                )
    except WebSocketDisconnect:
        pass
    finally:
        _room_connections[room_id].pop(connection_id, None)
        # Prune the empty room entry to keep memory lean.
        if not _room_connections[room_id]:
            del _room_connections[room_id]


# ---------------------------------------------------------------------------
# Action handlers (stubs — full implementation in game-state WOs)
# ---------------------------------------------------------------------------


async def _handle_roll_request(
    websocket: WebSocket,
    room_id: str,
    message: dict[str, Any],
    redis_client: aioredis.Redis,  # type: ignore[type-arg]
) -> None:
    """Stub: full implementation provided by the GameStateMachine (WO-011)."""
    await websocket.send_text(
        json.dumps(
            {
                "type": "error",
                "code": "NOT_IMPLEMENTED",
                "message": "Roll handling not yet implemented",
            }
        )
    )


async def _handle_select_pawn(
    websocket: WebSocket,
    room_id: str,
    message: dict[str, Any],
    redis_client: aioredis.Redis,  # type: ignore[type-arg]
) -> None:
    """Stub: full implementation provided by the GameStateMachine (WO-011)."""
    await websocket.send_text(
        json.dumps(
            {
                "type": "error",
                "code": "NOT_IMPLEMENTED",
                "message": "Pawn selection not yet implemented",
            }
        )
    )


async def _handle_chat(
    websocket: WebSocket,
    room_id: str,
    message: dict[str, Any],
    redis_client: aioredis.Redis,  # type: ignore[type-arg]
) -> None:
    """Broadcast a chat message to all clients in the room."""
    text = str(message.get("text", ""))[:500]  # hard cap to prevent abuse
    await broadcast_to_room(room_id, {"type": "chat", "from": "player", "text": text})
