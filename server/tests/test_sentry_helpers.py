"""Unit tests for Sentry WebSocket context helpers.

Covers:
- room_id tag is attached to every event
- user_id is attached only when provided (PII constraint: only ID, no email)
- Exceptions are captured and re-raised so callers can handle them
- No user context is set when user_id is None
"""

from unittest.mock import MagicMock, patch

import pytest

from app.sentry_helpers import websocket_sentry_context


def _make_mock_scope() -> MagicMock:
    """Return a MagicMock that behaves as a Sentry scope context manager."""
    mock_scope = MagicMock()
    return mock_scope


# ---------------------------------------------------------------------------
# Room ID tagging
# ---------------------------------------------------------------------------


def test_room_id_tag_is_set_on_scope() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with websocket_sentry_context(room_id="room-abc"):
            pass

    mock_scope.set_tag.assert_called_once_with("room_id", "room-abc")


def test_room_id_tag_reflects_passed_value() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with websocket_sentry_context(room_id="unique-room-xyz"):
            pass

    mock_scope.set_tag.assert_called_once_with("room_id", "unique-room-xyz")


# ---------------------------------------------------------------------------
# User ID — only ID, never PII
# ---------------------------------------------------------------------------


def test_user_id_is_set_when_provided() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with websocket_sentry_context(room_id="room-1", user_id="user-999"):
            pass

    # Must only contain the id — no email or display_name.
    mock_scope.set_user.assert_called_once_with({"id": "user-999"})


def test_user_id_is_not_set_when_none() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with websocket_sentry_context(room_id="room-1"):
            pass

    mock_scope.set_user.assert_not_called()


# ---------------------------------------------------------------------------
# Exception capture and re-raise
# ---------------------------------------------------------------------------


def test_exception_inside_context_is_captured() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with pytest.raises(ValueError):
            with websocket_sentry_context(room_id="room-1"):
                raise ValueError("ws protocol error")

    mock_sdk.capture_exception.assert_called_once()


def test_exception_inside_context_is_reraised() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    original_exc = RuntimeError("game state corruption")
    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with pytest.raises(RuntimeError, match="game state corruption"):
            with websocket_sentry_context(room_id="room-1"):
                raise original_exc


def test_no_exception_does_not_call_capture() -> None:
    mock_scope = _make_mock_scope()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_scope)
    cm.__exit__ = MagicMock(return_value=False)

    with patch("app.sentry_helpers.sentry_sdk") as mock_sdk:
        mock_sdk.new_scope.return_value = cm
        with websocket_sentry_context(room_id="room-1"):
            pass

    mock_sdk.capture_exception.assert_not_called()
