"""Tests for WebSocket message Pydantic schemas and the validate_ws_message helper.

Covers:
- Valid messages parse to the correct typed model.
- Invalid JSON raises ValueError.
- Messages with unknown or missing fields are rejected.
- Strict mode: no implicit type coercion (e.g. "1" is not accepted for pawn_id int).
- Text length limits on ChatMessage.
"""

import json

import pytest

from app.schemas.ws_messages import (
    ChatMessage,
    PingMessage,
    RollRequestMessage,
    SelectPawnMessage,
    validate_ws_message,
)


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------


def test_roll_request_parsed() -> None:
    msg = validate_ws_message(json.dumps({"type": "roll_request"}))
    assert isinstance(msg, RollRequestMessage)


def test_select_pawn_parsed() -> None:
    msg = validate_ws_message(json.dumps({"type": "select_pawn", "pawn_id": 2}))
    assert isinstance(msg, SelectPawnMessage)
    assert msg.pawn_id == 2


def test_chat_message_parsed() -> None:
    msg = validate_ws_message(json.dumps({"type": "chat", "text": "hello"}))
    assert isinstance(msg, ChatMessage)
    assert msg.text == "hello"


def test_ping_parsed() -> None:
    msg = validate_ws_message(json.dumps({"type": "ping"}))
    assert isinstance(msg, PingMessage)


# ---------------------------------------------------------------------------
# Invalid JSON
# ---------------------------------------------------------------------------


def test_invalid_json_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Invalid JSON"):
        validate_ws_message("not-json{{{")


def test_empty_string_raises_value_error() -> None:
    with pytest.raises(ValueError):
        validate_ws_message("")


# ---------------------------------------------------------------------------
# Unknown / missing fields
# ---------------------------------------------------------------------------


def test_unknown_type_raises_value_error() -> None:
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "hack_server"}))


def test_missing_pawn_id_raises_value_error() -> None:
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "select_pawn"}))


def test_missing_chat_text_raises_value_error() -> None:
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "chat"}))


# ---------------------------------------------------------------------------
# Strict mode — no implicit type coercion
# ---------------------------------------------------------------------------


def test_pawn_id_string_rejected_by_strict_mode() -> None:
    """Strict mode: string "1" must not be coerced to int for pawn_id."""
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "select_pawn", "pawn_id": "1"}))


def test_pawn_id_float_rejected_by_strict_mode() -> None:
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "select_pawn", "pawn_id": 1.5}))


# ---------------------------------------------------------------------------
# Field constraints
# ---------------------------------------------------------------------------


def test_chat_text_too_long_rejected() -> None:
    """Chat messages exceeding 500 characters are rejected."""
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "chat", "text": "x" * 501}))


def test_chat_empty_text_rejected() -> None:
    """Chat messages with empty text are rejected (min_length=1)."""
    with pytest.raises(ValueError):
        validate_ws_message(json.dumps({"type": "chat", "text": ""}))


def test_chat_text_at_max_length_accepted() -> None:
    msg = validate_ws_message(json.dumps({"type": "chat", "text": "a" * 500}))
    assert isinstance(msg, ChatMessage)
