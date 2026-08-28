"""WebSocket route for real-time in-game communication.

Each active room gets a dedicated WebSocket endpoint.  Every incoming message
is timed and the elapsed duration is recorded as ``ws_message_latency_ms`` in
the AshtaChamma/WebSocket CloudWatch namespace.

Architecture layer: routes (thin — parse message, call service, send response).
Game logic dispatch will be filled in by WO-004 and subsequent work orders.
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])

WS_NAMESPACE = "AshtaChamma/WebSocket"

# Buffer of latency samples waiting to be flushed.  The event loop is
# single-threaded so plain list mutation is safe (no lock needed here).
_ws_latency_buffer: list[float] = []

# Trigger an eager flush when the buffer reaches this size to bound memory use.
# Normal flush cadence (60 s) is handled by the background task in main.py.
_WS_BUFFER_FLUSH_THRESHOLD = 500


def get_ws_latency_buffer() -> list[float]:
    """Return a copy of the current WebSocket latency buffer.

    Exposed for testing so callers can inspect buffered samples.
    """
    return list(_ws_latency_buffer)


def clear_ws_latency_buffer() -> None:
    """Clear the WebSocket latency buffer (used in tests and by the flush task)."""
    _ws_latency_buffer.clear()


def flush_ws_metrics(cloudwatch_client: Any | None = None) -> None:
    """Publish buffered WebSocket latency samples to CloudWatch and clear the buffer.

    Args:
        cloudwatch_client: Injected boto3 CloudWatch client (for testing).
    """
    if not _ws_latency_buffer:
        return

    latencies = list(_ws_latency_buffer)
    _ws_latency_buffer.clear()

    if cloudwatch_client is None:
        import boto3  # noqa: PLC0415

        cloudwatch_client = boto3.client("cloudwatch")

    from botocore.exceptions import BotoCoreError, ClientError  # noqa: PLC0415

    metric_data = [
        {"MetricName": "ws_message_latency_ms", "Value": lat, "Unit": "Milliseconds"}
        for lat in latencies
    ]

    chunk_size = 20
    for i in range(0, len(metric_data), chunk_size):
        try:
            cloudwatch_client.put_metric_data(
                Namespace=WS_NAMESPACE,
                MetricData=metric_data[i : i + chunk_size],
            )
        except (BotoCoreError, ClientError) as exc:
            logger.warning("Failed to publish WebSocket metrics to CloudWatch: %s", exc)


def _record_ws_latency(elapsed_ms: float) -> None:
    """Append a latency sample to the buffer; flush early if threshold is reached."""
    _ws_latency_buffer.append(elapsed_ms)
    if len(_ws_latency_buffer) >= _WS_BUFFER_FLUSH_THRESHOLD:
        flush_ws_metrics()


@router.websocket("/rooms/{room_id}")
async def websocket_room(websocket: WebSocket, room_id: str) -> None:
    """WebSocket endpoint for real-time game communication within a room.

    Accepts connections, receives JSON messages, measures per-message processing
    time, and records it via ``_record_ws_latency``.

    Game state machine dispatch (roll, move, chat) will be wired in by WO-004
    and subsequent work orders.  Until then, unknown message types receive a
    NOT_IMPLEMENTED error response so the WebSocket contract is preserved.

    Args:
        websocket: The active WebSocket connection.
        room_id: UUID of the game room (validated by RoomManager in a later WO).
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted: room_id=%s", room_id)

    try:
        while True:
            message: dict[str, Any] = await websocket.receive_json()
            start = time.perf_counter()

            msg_type: str = message.get("type", "")
            logger.debug("Received WS message: type=%s room_id=%s", msg_type, room_id)

            # Game logic dispatch — stubbed pending WO-004+
            # Each handled type will record its own elapsed time before calling
            # _record_ws_latency so the measurement includes processing cost.
            response_payload = _dispatch_message(msg_type, message, room_id)

            elapsed_ms = (time.perf_counter() - start) * 1_000.0
            _record_ws_latency(elapsed_ms)

            await websocket.send_json(response_payload)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: room_id=%s", room_id)
    except Exception as exc:
        logger.exception("WebSocket error: room_id=%s error=%s", room_id, exc)
        await websocket.close(code=1011)


def _dispatch_message(
    msg_type: str, message: dict[str, Any], room_id: str
) -> dict[str, Any]:
    """Route a WebSocket message to the appropriate handler.

    Returns a response payload dict.  Stub implementation — game logic
    handlers (roll_request, select_pawn, chat, ping) will replace this
    in subsequent work orders.

    Args:
        msg_type: The ``type`` field from the incoming JSON message.
        message: Full message dict.
        room_id: Active room identifier.

    Returns:
        JSON-serialisable response dict.
    """
    if msg_type == "ping":
        return {"type": "pong"}

    # All other types are not yet implemented
    logger.debug("Unhandled WS message type=%s room_id=%s", msg_type, room_id)
    return {
        "type": "error",
        "code": "NOT_IMPLEMENTED",
        "message": f"Message type '{msg_type}' is not yet implemented.",
    }
