"""Tests for the WebSocket chat handler.

Covers:
- HTML-tag stripping / XSS sanitization
- Message length enforcement
- Empty-message rejection
- Broadcast delivery to all room members
- Per-message payload shape (type, sender_name, sender_color, text, timestamp)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routes.websocket import (
    _MAX_CHAT_LENGTH,
    _broadcast_to_room,
    _handle_chat,
    _room_connections,
    _sanitize_chat_text,
)


# ---------------------------------------------------------------------------
# _sanitize_chat_text unit tests
# ---------------------------------------------------------------------------


def test_sanitize_removes_simple_tag() -> None:
    """<b>…</b> tags are stripped, leaving only inner text."""
    assert _sanitize_chat_text("<b>hello</b>") == "hello"


def test_sanitize_removes_script_tag() -> None:
    """<script> injection attempt is neutralised."""
    result = _sanitize_chat_text('<script>alert("xss")</script>clean text')
    assert "<script>" not in result
    assert "</script>" not in result
    assert "clean text" in result


def test_sanitize_removes_self_closing_tag() -> None:
    assert _sanitize_chat_text("text<br/>more") == "textmore"


def test_sanitize_trims_whitespace() -> None:
    assert _sanitize_chat_text("  hello  ") == "hello"


def test_sanitize_preserves_plain_text() -> None:
    assert _sanitize_chat_text("Hello, world!") == "Hello, world!"


def test_sanitize_empty_string_returns_empty() -> None:
    assert _sanitize_chat_text("") == ""


def test_sanitize_only_tags_returns_empty() -> None:
    """A message that consists solely of HTML tags becomes empty after stripping."""
    assert _sanitize_chat_text("<b></b>") == ""


def test_sanitize_preserves_emoji() -> None:
    assert _sanitize_chat_text("🎲 good roll!") == "🎲 good roll!"


# ---------------------------------------------------------------------------
# _handle_chat — validation error paths
# ---------------------------------------------------------------------------


def _make_websocket() -> AsyncMock:
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


def _make_player(
    display_name: str = "Alice",
    color: str = "#e74c3c",
    user_id: str = "user-1",
) -> dict[str, str]:
    return {"display_name": display_name, "color": color, "user_id": user_id}


@pytest.mark.asyncio
async def test_handle_chat_rejects_non_string_text() -> None:
    ws = _make_websocket()
    await _handle_chat(ws, "room-1", _make_player(), {"type": "chat", "text": 42})
    ws.send_json.assert_awaited_once()
    sent: dict[str, Any] = ws.send_json.call_args[0][0]
    assert sent["type"] == "error"
    assert sent["code"] == "INVALID_CHAT"


@pytest.mark.asyncio
async def test_handle_chat_rejects_empty_message() -> None:
    ws = _make_websocket()
    await _handle_chat(ws, "room-1", _make_player(), {"type": "chat", "text": "   "})
    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "error"
    assert sent["code"] == "EMPTY_MESSAGE"


@pytest.mark.asyncio
async def test_handle_chat_rejects_message_exceeding_max_length() -> None:
    ws = _make_websocket()
    long_text = "a" * (_MAX_CHAT_LENGTH + 1)
    await _handle_chat(ws, "room-1", _make_player(), {"type": "chat", "text": long_text})
    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "error"
    assert sent["code"] == "MESSAGE_TOO_LONG"


@pytest.mark.asyncio
async def test_handle_chat_rejects_message_that_is_max_length_after_stripping() -> None:
    """A message exactly at the limit after tag-stripping is accepted."""
    ws = _make_websocket()
    exact_text = "a" * _MAX_CHAT_LENGTH
    with patch(
        "app.routes.websocket._broadcast_to_room", new_callable=AsyncMock
    ) as mock_broadcast:
        await _handle_chat(ws, "room-1", _make_player(), {"type": "chat", "text": exact_text})
    mock_broadcast.assert_awaited_once()
    ws.send_json.assert_not_awaited()  # No error was sent back to sender


@pytest.mark.asyncio
async def test_handle_chat_html_tags_stripped_before_length_check() -> None:
    """Tags are stripped *before* the length check; a long tag shouldn't
    cause a TOO_LONG error if the resulting plain text is within limits."""
    ws = _make_websocket()
    # 500 chars of tag markup whose stripped form is only "hi" (2 chars)
    tag_heavy = "<" + "a" * 498 + ">hi"
    with patch(
        "app.routes.websocket._broadcast_to_room", new_callable=AsyncMock
    ) as mock_broadcast:
        await _handle_chat(ws, "room-1", _make_player(), {"type": "chat", "text": tag_heavy})
    mock_broadcast.assert_awaited_once()


# ---------------------------------------------------------------------------
# _handle_chat — successful broadcast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handle_chat_broadcasts_to_all_room_members() -> None:
    """A valid chat message is forwarded to every connection in the room."""
    room_id = "test-room-broadcast"
    ws_sender = _make_websocket()
    ws_other1 = _make_websocket()
    ws_other2 = _make_websocket()

    player_sender = _make_player("Alice", "#e74c3c", "u1")
    player_other1 = _make_player("Bob", "#3498db", "u2")
    player_other2 = _make_player("Carol", "#2ecc71", "u3")

    _room_connections[room_id] = [
        (ws_sender, player_sender),
        (ws_other1, player_other1),
        (ws_other2, player_other2),
    ]

    try:
        await _handle_chat(
            ws_sender, room_id, player_sender, {"type": "chat", "text": "Hello room!"}
        )

        # All three connections receive the broadcast
        for ws in (ws_sender, ws_other1, ws_other2):
            ws.send_json.assert_awaited_once()
            payload = ws.send_json.call_args[0][0]
            assert payload["type"] == "chat_broadcast"
            assert payload["sender_name"] == "Alice"
            assert payload["sender_color"] == "#e74c3c"
            assert payload["text"] == "Hello room!"
            assert "timestamp" in payload
    finally:
        _room_connections.pop(room_id, None)


@pytest.mark.asyncio
async def test_handle_chat_broadcast_payload_has_required_fields() -> None:
    """Broadcast payload includes type, sender_name, sender_color, text, timestamp."""
    room_id = "test-room-fields"
    ws = _make_websocket()
    player = _make_player("Dave", "#9b59b6")
    _room_connections[room_id] = [(ws, player)]

    try:
        await _handle_chat(ws, room_id, player, {"type": "chat", "text": "Test"})
        payload = ws.send_json.call_args[0][0]
        for field in ("type", "sender_name", "sender_color", "text", "timestamp"):
            assert field in payload, f"Missing field: {field}"
        assert payload["type"] == "chat_broadcast"
    finally:
        _room_connections.pop(room_id, None)


@pytest.mark.asyncio
async def test_handle_chat_strips_html_tags_in_broadcast() -> None:
    """HTML tags in the message are stripped before the text is broadcast."""
    room_id = "test-room-strip"
    ws = _make_websocket()
    player = _make_player()
    _room_connections[room_id] = [(ws, player)]

    try:
        await _handle_chat(
            ws, room_id, player, {"type": "chat", "text": "<b>bold</b> text"}
        )
        payload = ws.send_json.call_args[0][0]
        assert "<b>" not in payload["text"]
        assert "</b>" not in payload["text"]
        assert "bold" in payload["text"]
        assert "text" in payload["text"]
    finally:
        _room_connections.pop(room_id, None)


# ---------------------------------------------------------------------------
# _broadcast_to_room — stale connection cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_removes_stale_connections() -> None:
    """Connections that raise on send_json are removed from the room registry."""
    room_id = "test-room-stale"
    ws_good = _make_websocket()
    ws_bad = _make_websocket()
    ws_bad.send_json.side_effect = RuntimeError("connection closed")

    player_good = _make_player("Good", "#fff", "g")
    player_bad = _make_player("Bad", "#000", "b")
    _room_connections[room_id] = [
        (ws_good, player_good),
        (ws_bad, player_bad),
    ]

    try:
        await _broadcast_to_room(room_id, {"type": "chat_broadcast", "text": "hi"})

        # Stale connection removed; healthy one remains
        remaining = _room_connections[room_id]
        assert (ws_good, player_good) in remaining
        assert (ws_bad, player_bad) not in remaining
    finally:
        _room_connections.pop(room_id, None)
