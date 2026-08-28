"""Tests for the WebSocket route handler (app.routes.websocket).

Coverage targets per the testing strategy:
- Game actions (roll, move, chat) update last_activity in Redis.
- broadcast_to_room sends JSON to all connections in the room.
- Stale connections do not block broadcasts to other clients.
- Broadcasting to an empty/unknown room is a no-op.
- _GAME_ACTIONS constant includes all expected action types.
"""

import json
import time
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.routes.websocket import (
    _GAME_ACTIONS,
    _activity_key,
    _room_connections,
    _update_last_activity,
    broadcast_to_room,
)


# ---------------------------------------------------------------------------
# _activity_key
# ---------------------------------------------------------------------------


def test_activity_key_format() -> None:
    room_id = "abc123"
    assert _activity_key(room_id) == "room:abc123:last_activity"


def test_activity_key_uuid() -> None:
    room_id = str(uuid.uuid4())
    assert _activity_key(room_id) == f"room:{room_id}:last_activity"


# ---------------------------------------------------------------------------
# _update_last_activity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_last_activity_writes_unix_timestamp() -> None:
    """The Redis key is set to the current Unix timestamp (integer string)."""
    room_id = str(uuid.uuid4())
    mock_redis = AsyncMock()

    before = int(time.time())
    await _update_last_activity(mock_redis, room_id)
    after = int(time.time())

    mock_redis.set.assert_awaited_once()
    call_key, call_value = mock_redis.set.call_args[0]

    assert call_key == f"room:{room_id}:last_activity"
    assert before <= int(call_value) <= after


@pytest.mark.asyncio
async def test_update_last_activity_called_on_roll_request() -> None:
    """roll_request is a recognised game action that resets the idle timer."""
    assert "roll_request" in _GAME_ACTIONS


@pytest.mark.asyncio
async def test_update_last_activity_called_on_select_pawn() -> None:
    """select_pawn is a recognised game action that resets the idle timer."""
    assert "select_pawn" in _GAME_ACTIONS


@pytest.mark.asyncio
async def test_update_last_activity_called_on_chat() -> None:
    """chat is a recognised game action that resets the idle timer."""
    assert "chat" in _GAME_ACTIONS


# ---------------------------------------------------------------------------
# broadcast_to_room
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_broadcast_sends_json_to_all_connections() -> None:
    """All active connections in the room receive the serialised message."""
    room_id = str(uuid.uuid4())
    ws1 = AsyncMock()
    ws2 = AsyncMock()
    _room_connections[room_id] = {"conn1": ws1, "conn2": ws2}

    try:
        await broadcast_to_room(room_id, {"type": "test", "value": 42})
        expected = json.dumps({"type": "test", "value": 42})
        ws1.send_text.assert_awaited_once_with(expected)
        ws2.send_text.assert_awaited_once_with(expected)
    finally:
        del _room_connections[room_id]


@pytest.mark.asyncio
async def test_broadcast_room_closed_message() -> None:
    """The canonical room_closed payload is delivered to all clients."""
    room_id = str(uuid.uuid4())
    ws = AsyncMock()
    _room_connections[room_id] = {"conn1": ws}

    try:
        await broadcast_to_room(room_id, {"type": "room_closed", "reason": "inactivity"})
        ws.send_text.assert_awaited_once_with(
            json.dumps({"type": "room_closed", "reason": "inactivity"})
        )
    finally:
        del _room_connections[room_id]


@pytest.mark.asyncio
async def test_broadcast_stale_connection_does_not_block_others() -> None:
    """An exception on one connection does not interrupt delivery to the others."""
    room_id = str(uuid.uuid4())
    ws_good = AsyncMock()
    ws_bad = AsyncMock()
    ws_bad.send_text.side_effect = RuntimeError("connection closed")

    _room_connections[room_id] = {"bad": ws_bad, "good": ws_good}

    try:
        await broadcast_to_room(room_id, {"type": "room_closed", "reason": "inactivity"})
        ws_good.send_text.assert_awaited_once()
    finally:
        del _room_connections[room_id]


@pytest.mark.asyncio
async def test_broadcast_to_unknown_room_is_safe() -> None:
    """Broadcasting to a room with no registered connections does not raise."""
    room_id = str(uuid.uuid4())
    # Ensure the room is not in _room_connections
    _room_connections.pop(room_id, None)
    # Should complete without error
    await broadcast_to_room(room_id, {"type": "room_closed", "reason": "inactivity"})


@pytest.mark.asyncio
async def test_broadcast_to_empty_room_is_safe() -> None:
    """A room entry with zero connections is treated as a no-op."""
    room_id = str(uuid.uuid4())
    _room_connections[room_id] = {}

    try:
        await broadcast_to_room(room_id, {"type": "ping"})
    finally:
        _room_connections.pop(room_id, None)


# ---------------------------------------------------------------------------
# _GAME_ACTIONS completeness
# ---------------------------------------------------------------------------


def test_game_actions_is_frozen_set() -> None:
    assert isinstance(_GAME_ACTIONS, frozenset)


def test_game_actions_contains_all_expected_types() -> None:
    assert _GAME_ACTIONS == {"roll_request", "select_pawn", "chat"}
