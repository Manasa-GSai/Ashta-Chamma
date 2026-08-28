"""WebSocket endpoint for real-time game communication.

Every player and spectator in a room connects to this endpoint.  Messages
are dispatched according to sender role:

  Spectators  → may only send 'chat' and 'ping'
  Players     → may send any message type

Game-action messages (roll_request, select_pawn) sent by spectators are
rejected immediately with an error envelope.  The rejection does NOT close
the connection — spectators remain connected and continue to receive all
broadcasts.

All outbound broadcasts are fanned out to every WebSocket registered for the
room.  In production the fan-out is done via Redis pub/sub so that messages
cross ECS Fargate task boundaries; the in-process registry used here is
equivalent for single-task deployments and tests.
"""

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services import room_service

logger = logging.getLogger(__name__)
router = APIRouter()

# In-process connection registry.
# Key: room_code, Value: list of (user_id, WebSocket) pairs.
# Each pair represents one active connection.
_room_connections: dict[str, list[tuple[str, WebSocket]]] = {}

# Message types that mutate game state — blocked for spectators.
_GAME_ACTION_TYPES: frozenset[str] = frozenset({"roll_request", "select_pawn"})


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _broadcast(room_code: str, message: dict[str, Any]) -> None:
    """Send a JSON message to every active connection in the room.

    Stale connections (those that raise on send) are pruned from the
    registry so they do not slow future broadcasts.
    """
    connections = _room_connections.get(room_code, [])
    stale: list[tuple[str, WebSocket]] = []

    for uid, ws in connections:
        try:
            await ws.send_json(message)
        except Exception:
            stale.append((uid, ws))

    if stale:
        _room_connections[room_code] = [c for c in connections if c not in stale]


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/rooms/{room_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str) -> None:
    """WebSocket endpoint for real-time game communication.

    Callers supply identity via query parameters:
      user_id      — required; the authenticated user's ID
      display_name — optional; defaults to "Anonymous"

    Connection is rejected (4004) when the room_code is unknown.
    """
    user_id: str = websocket.query_params.get("user_id", "anonymous")
    display_name: str = websocket.query_params.get("display_name", "Anonymous")

    # Validate room exists before accepting the upgrade
    room = room_service.get_room(room_code)
    if room is None:
        await websocket.close(code=4004, reason="Room not found")
        return

    await websocket.accept()

    # Register connection
    _room_connections.setdefault(room_code, []).append((user_id, websocket))

    spectator: bool = room_service.is_spectator(room_code, user_id)

    # Send the connecting client the current room state together with their
    # spectator flag so the frontend can initialise correctly.
    await websocket.send_json(
        {
            "type": "state_update",
            "state": room_service.get_room(room_code),
            "is_spectator": spectator,
        }
    )

    try:
        while True:
            data: dict[str, Any] = await websocket.receive_json()
            msg_type: str = data.get("type", "")

            if msg_type in _GAME_ACTION_TYPES:
                # Spectators must not influence game state
                if spectator:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "Spectators cannot perform game actions",
                        }
                    )
                    continue

                # In a full implementation the game state machine processes the
                # action and a state delta is published via Redis pub/sub.
                # Here we echo a broadcast so tests can verify fan-out.
                await _broadcast(
                    room_code,
                    {
                        "type": "state_update",
                        "state": room_service.get_room(room_code),
                        "action": msg_type,
                        "from": user_id,
                    },
                )

            elif msg_type == "chat":
                # Chat is available to both players and spectators
                text: str = data.get("text", "")
                await _broadcast(
                    room_code,
                    {"type": "chat", "from": display_name, "text": text},
                )

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json(
                    {"type": "error", "message": f"Unknown message type: {msg_type}"}
                )

    except WebSocketDisconnect:
        _remove_connection(room_code, user_id, websocket)
        logger.info("User %s disconnected from room %s", user_id, room_code)

    except Exception as exc:
        _remove_connection(room_code, user_id, websocket)
        logger.error(
            "WebSocket error for user %s in room %s: %s", user_id, room_code, exc
        )


def _remove_connection(
    room_code: str, user_id: str, websocket: WebSocket
) -> None:
    """Remove a single connection entry from the registry."""
    connections = _room_connections.get(room_code, [])
    _room_connections[room_code] = [
        (uid, ws)
        for uid, ws in connections
        if not (uid == user_id and ws is websocket)
    ]


def get_room_connections(room_code: str) -> list[tuple[str, WebSocket]]:
    """Return active connections for a room.  Used in tests."""
    return list(_room_connections.get(room_code, []))


def clear_connections() -> None:
    """Clear the entire connection registry.  Used in tests."""
    _room_connections.clear()
