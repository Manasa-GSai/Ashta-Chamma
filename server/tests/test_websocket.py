"""Tests for the WebSocket route handler.

Covers:
- Valid messages are accepted and handled (ping → pong).
- Invalid messages return {type: 'error', message: 'Invalid message format'}.
- Per-connection rate limiting: 11th message in 1 second receives an error frame.
- Room ID is used in the endpoint URL (path parameter routing works).
"""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app

_client = TestClient(app)


# ---------------------------------------------------------------------------
# Ping / pong
# ---------------------------------------------------------------------------


def test_ping_returns_pong() -> None:
    with _client.websocket_connect("/ws/rooms/test-room-1") as ws:
        ws.send_text(json.dumps({"type": "ping"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "pong"


# ---------------------------------------------------------------------------
# Invalid message schema
# ---------------------------------------------------------------------------


def test_invalid_json_returns_error_frame() -> None:
    with _client.websocket_connect("/ws/rooms/test-room-2") as ws:
        ws.send_text("not-valid-json{{{")
        data = json.loads(ws.receive_text())
        assert data["type"] == "error"
        assert data["message"] == "Invalid message format"


def test_unknown_message_type_returns_error_frame() -> None:
    with _client.websocket_connect("/ws/rooms/test-room-3") as ws:
        ws.send_text(json.dumps({"type": "unknown_command"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "error"
        assert data["message"] == "Invalid message format"


def test_missing_required_field_returns_error_frame() -> None:
    """select_pawn without pawn_id should return an error frame."""
    with _client.websocket_connect("/ws/rooms/test-room-4") as ws:
        ws.send_text(json.dumps({"type": "select_pawn"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "error"
        assert data["message"] == "Invalid message format"


def test_strict_type_rejection_returns_error_frame() -> None:
    """pawn_id passed as string should fail strict validation."""
    with _client.websocket_connect("/ws/rooms/test-room-5") as ws:
        ws.send_text(json.dumps({"type": "select_pawn", "pawn_id": "two"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "error"
        assert data["message"] == "Invalid message format"


# ---------------------------------------------------------------------------
# WebSocket rate limiting
# ---------------------------------------------------------------------------


def test_rate_limit_drops_excess_messages() -> None:
    """Sending 11 pings in rapid succession should trigger a rate-limit error."""
    from app.routes.websocket import _WS_RATE_LIMIT

    with _client.websocket_connect("/ws/rooms/rate-limit-room") as ws:
        responses = []
        # Send _WS_RATE_LIMIT + 1 messages; the last one should be rate-limited.
        for _ in range(_WS_RATE_LIMIT + 1):
            ws.send_text(json.dumps({"type": "ping"}))

        # Collect all responses
        for _ in range(_WS_RATE_LIMIT + 1):
            responses.append(json.loads(ws.receive_text()))

        types = [r["type"] for r in responses]
        # The excess message should trigger an error response
        assert "error" in types
        # At least some pongs should have succeeded
        assert "pong" in types


def test_rate_limit_error_message_content() -> None:
    """The rate-limit error frame contains an informative message."""
    from app.routes.websocket import _WS_RATE_LIMIT

    with _client.websocket_connect("/ws/rooms/rate-limit-msg-room") as ws:
        for _ in range(_WS_RATE_LIMIT + 1):
            ws.send_text(json.dumps({"type": "ping"}))

        error_found = False
        for _ in range(_WS_RATE_LIMIT + 1):
            data = json.loads(ws.receive_text())
            if data["type"] == "error" and "rate limit" in data["message"].lower():
                error_found = True
                break

        assert error_found, "Expected a rate-limit error frame but did not receive one"


# ---------------------------------------------------------------------------
# Valid non-ping messages (no crash path)
# ---------------------------------------------------------------------------


def test_roll_request_accepted_without_crash() -> None:
    """roll_request is a valid message and must not crash the handler."""
    with _client.websocket_connect("/ws/rooms/roll-room") as ws:
        ws.send_text(json.dumps({"type": "roll_request"}))
        # No response expected yet (game logic stub); just verify no crash.
        ws.send_text(json.dumps({"type": "ping"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "pong"


def test_chat_message_accepted_without_crash() -> None:
    with _client.websocket_connect("/ws/rooms/chat-room") as ws:
        ws.send_text(json.dumps({"type": "chat", "text": "Hello, world!"}))
        ws.send_text(json.dumps({"type": "ping"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "pong"


def test_select_pawn_accepted_without_crash() -> None:
    with _client.websocket_connect("/ws/rooms/select-room") as ws:
        ws.send_text(json.dumps({"type": "select_pawn", "pawn_id": 0}))
        ws.send_text(json.dumps({"type": "ping"}))
        data = json.loads(ws.receive_text())
        assert data["type"] == "pong"
