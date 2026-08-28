"""Tests for the idle-room cleanup task (app.tasks.cleanup).

Coverage targets per the testing strategy:
- Game actions update last_activity in Redis.
- Rooms idle >15 min are identified and abandoned.
- Cleanup transitions room to ``abandoned`` in PostgreSQL with ``ended_at``.
- Connected WebSocket clients receive the ``room_closed`` notification.
- Idempotency: already-closed rooms are not re-processed.
- Edge cases: Redis unavailable, key expires between scan/get, bad data.
"""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.tasks.cleanup import (
    _delete_redis_keys,
    _notify_clients,
    _parse_room_id_from_key,
    _persist_abandoned_status,
    cleanup_idle_rooms,
)


# ---------------------------------------------------------------------------
# _parse_room_id_from_key
# ---------------------------------------------------------------------------


def test_parse_room_id_valid_key() -> None:
    room_id = "abc123"
    assert _parse_room_id_from_key(f"room:{room_id}:last_activity") == room_id


def test_parse_room_id_uuid_key() -> None:
    room_id = str(uuid.uuid4())
    assert _parse_room_id_from_key(f"room:{room_id}:last_activity") == room_id


def test_parse_room_id_wrong_suffix_returns_none() -> None:
    assert _parse_room_id_from_key("room:abc:state") is None


def test_parse_room_id_too_few_parts_returns_none() -> None:
    assert _parse_room_id_from_key("room:abc") is None


def test_parse_room_id_plain_string_returns_none() -> None:
    assert _parse_room_id_from_key("invalid") is None


# ---------------------------------------------------------------------------
# cleanup_idle_rooms — idle room detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_abandons_idle_room() -> None:
    """A room whose last_activity exceeds the timeout is passed to _abandon_room."""
    room_id = str(uuid.uuid4())
    stale_ts = str(int(time.time()) - 1000)  # 1 000 s > 900 s threshold
    key = f"room:{room_id}:last_activity"

    mock_redis = AsyncMock()
    mock_redis.keys.return_value = [key]
    mock_redis.get.return_value = stale_ts

    with (
        patch("app.tasks.cleanup.get_redis", return_value=mock_redis),
        patch("app.tasks.cleanup._abandon_room", new_callable=AsyncMock) as mock_abandon,
    ):
        await cleanup_idle_rooms()
        mock_abandon.assert_awaited_once_with(room_id, mock_redis)


@pytest.mark.asyncio
async def test_cleanup_skips_active_room() -> None:
    """A room active within the last 15 min is NOT abandoned."""
    room_id = str(uuid.uuid4())
    recent_ts = str(int(time.time()) - 60)  # 60 s ago — well within threshold
    key = f"room:{room_id}:last_activity"

    mock_redis = AsyncMock()
    mock_redis.keys.return_value = [key]
    mock_redis.get.return_value = recent_ts

    with (
        patch("app.tasks.cleanup.get_redis", return_value=mock_redis),
        patch("app.tasks.cleanup._abandon_room", new_callable=AsyncMock) as mock_abandon,
    ):
        await cleanup_idle_rooms()
        mock_abandon.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_handles_redis_scan_error() -> None:
    """A Redis error during key scan is caught; no exception propagates."""
    import redis.asyncio as aioredis

    mock_redis = AsyncMock()
    mock_redis.keys.side_effect = aioredis.RedisError("connection refused")

    with patch("app.tasks.cleanup.get_redis", return_value=mock_redis):
        await cleanup_idle_rooms()  # must not raise


@pytest.mark.asyncio
async def test_cleanup_skips_key_expired_between_scan_and_get() -> None:
    """If GET returns None (key expired since KEYS), the room is silently skipped."""
    room_id = str(uuid.uuid4())
    key = f"room:{room_id}:last_activity"

    mock_redis = AsyncMock()
    mock_redis.keys.return_value = [key]
    mock_redis.get.return_value = None  # expired

    with (
        patch("app.tasks.cleanup.get_redis", return_value=mock_redis),
        patch("app.tasks.cleanup._abandon_room", new_callable=AsyncMock) as mock_abandon,
    ):
        await cleanup_idle_rooms()
        mock_abandon.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_skips_malformed_timestamp() -> None:
    """Non-integer last_activity values are skipped without raising."""
    room_id = str(uuid.uuid4())
    key = f"room:{room_id}:last_activity"

    mock_redis = AsyncMock()
    mock_redis.keys.return_value = [key]
    mock_redis.get.return_value = "not-a-number"

    with (
        patch("app.tasks.cleanup.get_redis", return_value=mock_redis),
        patch("app.tasks.cleanup._abandon_room", new_callable=AsyncMock) as mock_abandon,
    ):
        await cleanup_idle_rooms()
        mock_abandon.assert_not_called()


@pytest.mark.asyncio
async def test_cleanup_processes_multiple_idle_rooms() -> None:
    """All idle rooms in the scan are independently abandoned."""
    rooms = [str(uuid.uuid4()) for _ in range(3)]
    stale_ts = str(int(time.time()) - 2000)
    keys = [f"room:{r}:last_activity" for r in rooms]

    mock_redis = AsyncMock()
    mock_redis.keys.return_value = keys
    mock_redis.get.return_value = stale_ts

    with (
        patch("app.tasks.cleanup.get_redis", return_value=mock_redis),
        patch("app.tasks.cleanup._abandon_room", new_callable=AsyncMock) as mock_abandon,
    ):
        await cleanup_idle_rooms()
        assert mock_abandon.await_count == 3


# ---------------------------------------------------------------------------
# _persist_abandoned_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_abandoned_transitions_waiting_room() -> None:
    """A room in ``waiting`` status is updated to ``abandoned`` with ended_at."""
    from app.models.room import Room, RoomStatus

    room_id = str(uuid.uuid4())
    mock_room = MagicMock(spec=Room)
    mock_room.id = uuid.UUID(room_id)
    mock_room.status = RoomStatus.WAITING

    mock_session = _make_mock_session(mock_room)

    with patch("app.tasks.cleanup.AsyncSessionLocal", return_value=mock_session):
        result = await _persist_abandoned_status(room_id)

    assert result is True
    assert mock_room.status == RoomStatus.ABANDONED
    assert mock_room.ended_at is not None
    mock_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_persist_abandoned_transitions_in_progress_room() -> None:
    """A room in ``in_progress`` status is also moved to ``abandoned``."""
    from app.models.room import Room, RoomStatus

    room_id = str(uuid.uuid4())
    mock_room = MagicMock(spec=Room)
    mock_room.id = uuid.UUID(room_id)
    mock_room.status = RoomStatus.IN_PROGRESS

    mock_session = _make_mock_session(mock_room)

    with patch("app.tasks.cleanup.AsyncSessionLocal", return_value=mock_session):
        result = await _persist_abandoned_status(room_id)

    assert result is True
    assert mock_room.status == RoomStatus.ABANDONED


@pytest.mark.asyncio
async def test_persist_abandoned_idempotent_on_already_abandoned() -> None:
    """Rooms already ``abandoned`` return False; no extra audit log is written."""
    from app.models.room import Room, RoomStatus

    room_id = str(uuid.uuid4())
    mock_room = MagicMock(spec=Room)
    mock_room.id = uuid.UUID(room_id)
    mock_room.status = RoomStatus.ABANDONED

    mock_session = _make_mock_session(mock_room)

    with patch("app.tasks.cleanup.AsyncSessionLocal", return_value=mock_session):
        result = await _persist_abandoned_status(room_id)

    assert result is False
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_abandoned_idempotent_on_completed() -> None:
    """Rooms in ``completed`` status also return False."""
    from app.models.room import Room, RoomStatus

    room_id = str(uuid.uuid4())
    mock_room = MagicMock(spec=Room)
    mock_room.id = uuid.UUID(room_id)
    mock_room.status = RoomStatus.COMPLETED

    mock_session = _make_mock_session(mock_room)

    with patch("app.tasks.cleanup.AsyncSessionLocal", return_value=mock_session):
        result = await _persist_abandoned_status(room_id)

    assert result is False
    mock_session.add.assert_not_called()


@pytest.mark.asyncio
async def test_persist_abandoned_room_not_found_returns_false() -> None:
    """Missing rooms return False without raising."""
    room_id = str(uuid.uuid4())
    mock_session = _make_mock_session(None)

    with patch("app.tasks.cleanup.AsyncSessionLocal", return_value=mock_session):
        result = await _persist_abandoned_status(room_id)

    assert result is False


@pytest.mark.asyncio
async def test_persist_abandoned_invalid_uuid_returns_false() -> None:
    """A non-UUID room_id is rejected early, returning False."""
    result = await _persist_abandoned_status("not-a-uuid")
    assert result is False


# ---------------------------------------------------------------------------
# _notify_clients
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_notify_clients_broadcasts_room_closed_message() -> None:
    """Clients in the room receive ``{type: room_closed, reason: inactivity}``."""
    room_id = str(uuid.uuid4())

    with patch(
        "app.routes.websocket.broadcast_to_room", new_callable=AsyncMock
    ) as mock_broadcast:
        await _notify_clients(room_id)
        mock_broadcast.assert_awaited_once_with(
            room_id, {"type": "room_closed", "reason": "inactivity"}
        )


@pytest.mark.asyncio
async def test_notify_clients_broadcast_error_does_not_raise() -> None:
    """A broadcast failure is swallowed so cleanup can continue."""
    room_id = str(uuid.uuid4())

    with patch(
        "app.routes.websocket.broadcast_to_room",
        new_callable=AsyncMock,
        side_effect=RuntimeError("ws closed"),
    ):
        await _notify_clients(room_id)  # must not raise


# ---------------------------------------------------------------------------
# _delete_redis_keys
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_redis_keys_removes_all_expected_keys() -> None:
    """All four ephemeral keys are deleted in a single DEL call."""
    room_id = str(uuid.uuid4())
    mock_redis = AsyncMock()

    await _delete_redis_keys(room_id, mock_redis)

    deleted_keys = set(mock_redis.delete.call_args[0])
    expected = {
        f"room:{room_id}:state",
        f"room:{room_id}:players",
        f"room:{room_id}:chat",
        f"room:{room_id}:last_activity",
    }
    assert expected == deleted_keys


@pytest.mark.asyncio
async def test_delete_redis_keys_handles_redis_error() -> None:
    """A Redis error during deletion is caught and does not propagate."""
    import redis.asyncio as aioredis

    room_id = str(uuid.uuid4())
    mock_redis = AsyncMock()
    mock_redis.delete.side_effect = aioredis.RedisError("connection lost")

    await _delete_redis_keys(room_id, mock_redis)  # must not raise


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session(room_or_none: object) -> AsyncMock:
    """Build a minimal async context-manager mock for ``AsyncSessionLocal``."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = room_or_none

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute.return_value = mock_result
    mock_session.add = MagicMock()

    # ``session.begin()`` is an async context manager.
    mock_begin_ctx = AsyncMock()
    mock_begin_ctx.__aenter__ = AsyncMock(return_value=None)
    mock_begin_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session.begin.return_value = mock_begin_ctx

    return mock_session
