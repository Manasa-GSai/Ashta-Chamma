"""WebSocket route handler for real-time Ashta Chamma game communication.

Each room connection gets its own per-connection sliding window rate limiter
(10 messages/second) tracked entirely in process memory — this is intentional
because the limit is per *connection*, not per user, and does not need to be
shared across tasks.

All incoming messages are validated against the Pydantic schemas in
``app.schemas.ws_messages`` before dispatching to game logic handlers.
Invalid messages return an error frame instead of crashing the handler.

Logging of user-supplied values (room_id) uses ``_sanitize`` to prevent
log injection.
"""

import json
import logging
import time
from collections import deque

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.schemas.ws_messages import (
    ChatMessage,
    ErrorMessage,
    PingMessage,
    RollRequestMessage,
    SelectPawnMessage,
    validate_ws_message,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Per-connection WebSocket rate limit: 10 messages per second.
_WS_RATE_LIMIT: int = 10
_WS_RATE_WINDOW: float = 1.0  # seconds


def _is_rate_limited(message_timestamps: deque[float]) -> bool:
    """Check and update the per-connection sliding window rate limiter.

    Removes timestamps older than the 1-second window, then checks whether
    the connection has already sent *_WS_RATE_LIMIT* messages in that window.
    Appends the current timestamp only when the request is *not* rate-limited
    so dropped messages do not consume a slot.

    Returns:
        True if the message should be dropped (rate limit exceeded).
        False if the message is within limits (timestamp recorded).
    """
    now = time.monotonic()
    cutoff = now - _WS_RATE_WINDOW
    while message_timestamps and message_timestamps[0] < cutoff:
        message_timestamps.popleft()
    if len(message_timestamps) >= _WS_RATE_LIMIT:
        return True
    message_timestamps.append(now)
    return False


def _sanitize(value: str) -> str:
    """Return *value* with only alphanumeric characters and ``-_`` kept.

    Used before interpolating user-supplied strings into log messages to
    prevent log injection attacks.
    """
    return "".join(c for c in value if c.isalnum() or c in "-_")


@router.websocket("/ws/rooms/{room_id}")
async def websocket_room_endpoint(websocket: WebSocket, room_id: str) -> None:
    """Accept a WebSocket connection for a game room.

    Per-connection responsibilities:
    - Enforce 10 messages/second rate limit; drop excess with a warning frame.
    - Validate every message against the defined schema before dispatching.
    - Return ``{type: 'error', message: 'Invalid message format'}`` for bad messages.
    """
    await websocket.accept()
    message_timestamps: deque[float] = deque()
    safe_room_id = _sanitize(room_id)

    try:
        while True:
            raw = await websocket.receive_text()

            # Drop excess messages but notify the sender.
            if _is_rate_limited(message_timestamps):
                logger.warning(
                    "WebSocket rate limit exceeded: room=%s; dropping message",
                    safe_room_id,
                )
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Rate limit exceeded: slow down"})
                )
                continue

            # Validate message schema; send generic error on failure to avoid
            # leaking internal Pydantic error details to the client.
            try:
                message = validate_ws_message(raw)
            except ValueError:
                error = ErrorMessage(message="Invalid message format")
                await websocket.send_text(error.model_dump_json())
                continue

            await _dispatch(websocket, safe_room_id, message)

    except WebSocketDisconnect:
        logger.info("Client disconnected: room=%s", safe_room_id)


async def _dispatch(
    websocket: WebSocket,
    safe_room_id: str,
    message: RollRequestMessage | SelectPawnMessage | ChatMessage | PingMessage,
) -> None:
    """Route a validated message to the appropriate handler stub.

    Full game logic integration will be added in WO-016 (WebSocket handler
    with Redis pub/sub).  For now, only the ping/pong round-trip is
    implemented so the endpoint is functional and testable.
    """
    if isinstance(message, PingMessage):
        await websocket.send_text(json.dumps({"type": "pong"}))

    elif isinstance(message, RollRequestMessage):
        # TODO(WO-016): Delegate to GameStateMachine.handle_roll_request()
        logger.debug("Roll request received: room=%s", safe_room_id)

    elif isinstance(message, SelectPawnMessage):
        # TODO(WO-016): Delegate to GameStateMachine.handle_select_pawn()
        logger.debug(
            "Select pawn %d: room=%s",
            message.pawn_id,
            safe_room_id,
        )

    elif isinstance(message, ChatMessage):
        # TODO(WO-016): Broadcast via Redis pub/sub
        logger.debug("Chat received: room=%s", safe_room_id)
