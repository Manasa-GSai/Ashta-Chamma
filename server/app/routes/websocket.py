"""WebSocket route handler for real-time in-game communication.

All in-game communication — including game state updates, cowrie roll results,
and chat messages — flows through this module. Each room has its own broadcast
group; connections are stored in a module-level registry keyed by room_id.

Chat messages are ephemeral (not persisted to the database). HTML tags are
stripped before broadcast to prevent XSS. See OWASP A05 constraint in WO-025.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter()

# In-memory connection registry: room_id -> list of (websocket, player_info)
# player_info keys: user_id, display_name, color
# Replaced by Redis pub/sub when the PubSubBridge work order lands; keeping
# this in-memory for single-task correctness in the current phase.
_room_connections: dict[str, list[tuple[WebSocket, dict[str, str]]]] = defaultdict(list)

_MAX_CHAT_LENGTH: int = 200

# Regex to strip any HTML/XML-style tags.  Compiled once at module load.
_HTML_TAG_RE: re.Pattern[str] = re.compile(r"<[^>]*>")


def _sanitize_chat_text(text: str) -> str:
    """Strip HTML tags from *text* and trim surrounding whitespace.

    Removing tags (rather than escaping them) ensures the stored/broadcast
    value is plain text that React can render without double-encoding issues.
    Any residual `<` / `>` that were not part of a well-formed tag survive
    harmlessly as literal characters; the React client escapes them on render.

    Args:
        text: Raw chat message string received from the client.

    Returns:
        Sanitized plain-text string.
    """
    without_tags = _HTML_TAG_RE.sub("", text)
    return without_tags.strip()


async def _broadcast_to_room(room_id: str, message: dict[str, Any]) -> None:
    """Send *message* as JSON to every WebSocket client connected to *room_id*.

    Silently removes connections that fail to receive the message (the client
    has likely disconnected without sending a close frame).
    """
    stale: list[tuple[WebSocket, dict[str, str]]] = []
    for ws, player_info in list(_room_connections[room_id]):
        try:
            await ws.send_json(message)
        except Exception:
            logger.warning(
                "Failed to send message to player %s; marking connection stale",
                player_info.get("display_name"),
            )
            stale.append((ws, player_info))
    for item in stale:
        try:
            _room_connections[room_id].remove(item)
        except ValueError:
            pass  # Already removed by a concurrent handler


@router.websocket("/ws/rooms/{room_id}")
async def room_websocket(websocket: WebSocket, room_id: str) -> None:
    """Handle WebSocket connections for a specific game room.

    Query parameters accepted on upgrade:
    - ``token``: Clerk JWT (validated by AuthMiddleware in WO-016)
    - ``user_id``: Player UUID (placeholder until AuthMiddleware injects context)
    - ``display_name``: Player display name shown in chat
    - ``color``: Player colour hex string (e.g. ``#e74c3c``)
    """
    await websocket.accept()

    # Placeholder identity extraction from query params.
    # Full Clerk JWT validation and user-context injection is handled by the
    # auth middleware introduced in WO-016; these defaults maintain backwards
    # compatibility during the transition.
    player_info: dict[str, str] = {
        "user_id": websocket.query_params.get("user_id", "anonymous"),
        "display_name": websocket.query_params.get("display_name", "Player"),
        "color": websocket.query_params.get("color", "#ffffff"),
    }

    _room_connections[room_id].append((websocket, player_info))
    logger.info(
        "Client connected to room %s; player=%s",
        room_id,
        player_info["display_name"],
    )

    try:
        while True:
            data: Any = await websocket.receive_json()
            if isinstance(data, dict):
                await _handle_message(websocket, room_id, player_info, data)
    except WebSocketDisconnect:
        logger.info(
            "Client disconnected from room %s; player=%s",
            room_id,
            player_info["display_name"],
        )
    finally:
        connections = _room_connections.get(room_id, [])
        try:
            connections.remove((websocket, player_info))
        except ValueError:
            pass  # Already cleaned up by _broadcast_to_room


async def _handle_message(
    websocket: WebSocket,
    room_id: str,
    player_info: dict[str, str],
    data: dict[str, Any],
) -> None:
    """Dispatch an incoming WebSocket message to the appropriate sub-handler."""
    msg_type = data.get("type")

    if msg_type == "chat":
        await _handle_chat(websocket, room_id, player_info, data)
    elif msg_type == "ping":
        await websocket.send_json({"type": "pong"})
    else:
        logger.debug("Unhandled message type %r in room %s", msg_type, room_id)


async def _handle_chat(
    websocket: WebSocket,
    room_id: str,
    player_info: dict[str, str],
    data: dict[str, Any],
) -> None:
    """Validate and broadcast a chat message to every member of *room_id*.

    Validation rules (per WO-025 acceptance criteria):
    1. ``text`` field must be a string.
    2. After HTML-tag stripping, the message must be non-empty.
    3. Sanitized text must not exceed ``_MAX_CHAT_LENGTH`` characters.

    On success the broadcast payload type is ``chat_broadcast`` and includes
    ``sender_name``, ``sender_color``, ``text``, and an ISO-8601 UTC
    ``timestamp``.
    """
    raw_text: Any = data.get("text", "")

    if not isinstance(raw_text, str):
        await websocket.send_json(
            {
                "type": "error",
                "code": "INVALID_CHAT",
                "message": "Chat text must be a string.",
            }
        )
        return

    sanitized = _sanitize_chat_text(raw_text)

    if not sanitized:
        await websocket.send_json(
            {
                "type": "error",
                "code": "EMPTY_MESSAGE",
                "message": "Chat message cannot be empty.",
            }
        )
        return

    if len(sanitized) > _MAX_CHAT_LENGTH:
        await websocket.send_json(
            {
                "type": "error",
                "code": "MESSAGE_TOO_LONG",
                "message": f"Chat message exceeds the {_MAX_CHAT_LENGTH}-character limit.",
            }
        )
        return

    broadcast_payload: dict[str, Any] = {
        "type": "chat_broadcast",
        "sender_name": player_info["display_name"],
        "sender_color": player_info["color"],
        "text": sanitized,
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    await _broadcast_to_room(room_id, broadcast_payload)
