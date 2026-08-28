"""Tests for GameService.start_game (WO-015).

All external dependencies (room repository, Redis) are replaced with
AsyncMock fakes so no database or Redis server is required.

Test coverage:
  - Happy path: 2 players, 4 players (including AI)
  - Pawn initialisation at correct home positions
  - Room status updated to 'playing'
  - Game state set to ROLLING after start
  - Audit log entry created with action 'game.started'
  - GameSession persisted to Redis
  - Error: fewer than 2 players (HTTP 400)
  - Error: non-host requester (HTTP 403)
  - Error: game already started (HTTP 409)
  - Error: room not found (HTTP 404)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.game.board import HOME_POSITIONS, PAWNS_PER_PLAYER
from app.game.session import GameState
from app.models.enums import RoomStatus
from app.models.tables import Room, RoomPlayer
from app.services.game_service import GameService, GameStartError

# ---------------------------------------------------------------------------
# Constants shared across tests
# ---------------------------------------------------------------------------

_ROOM_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_HOST_ID = "22222222-2222-2222-2222-222222222222"
_HOST_UUID = uuid.UUID(_HOST_ID)
_PLAYER2_ID = "33333333-3333-3333-3333-333333333333"
_ROOM_CODE = "ABCDEF"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_room(
    status: str = RoomStatus.WAITING.value,
    host_user_id: uuid.UUID = _HOST_UUID,
) -> MagicMock:
    """Return a MagicMock that mimics a Room ORM object."""
    room = MagicMock(spec=Room)
    room.id = _ROOM_ID
    room.code = _ROOM_CODE
    room.host_user_id = host_user_id
    room.status = status
    return room


def _make_player(
    player_index: int,
    user_id: str | None = None,
    ai_persona_id: int | None = None,
) -> MagicMock:
    """Return a MagicMock that mimics a RoomPlayer ORM object."""
    colors = ["red", "blue", "green", "yellow"]
    rp = MagicMock(spec=RoomPlayer)
    rp.player_index = player_index
    rp.user_id = uuid.UUID(user_id) if user_id else None
    rp.ai_persona_id = ai_persona_id
    rp.color = colors[player_index % len(colors)]
    return rp


def _make_service(
    room: Room | None = None,
    players: list[RoomPlayer] | None = None,
) -> tuple[GameService, AsyncMock, AsyncMock]:
    """Build a GameService with mock repository and Redis.

    Returns (service, mock_room_repo, mock_redis).
    """
    mock_repo = AsyncMock()
    mock_repo.get_room_by_code.return_value = room
    mock_repo.get_room_players.return_value = players or []
    mock_repo.update_room_started.return_value = None
    mock_repo.create_audit_log.return_value = None

    mock_redis = AsyncMock()
    mock_redis.set.return_value = None
    mock_redis.get.return_value = None
    mock_redis.exists.return_value = False

    svc = GameService(room_repo=mock_repo, redis=mock_redis)
    return svc, mock_repo, mock_redis


def _two_player_setup() -> tuple[GameService, AsyncMock, AsyncMock]:
    room = _make_room()
    players = [
        _make_player(0, user_id=_HOST_ID),
        _make_player(1, user_id=_PLAYER2_ID),
    ]
    return _make_service(room=room, players=players)


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_game_with_two_human_players_succeeds() -> None:
    svc, _, _ = _two_player_setup()
    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)
    assert snapshot["state"] == GameState.ROLLING.value
    assert snapshot["current_player_index"] == 0
    assert len(snapshot["players"]) == 2


@pytest.mark.asyncio
async def test_start_game_with_four_players_includes_ai() -> None:
    room = _make_room()
    players = [
        _make_player(0, user_id=_HOST_ID),
        _make_player(1, user_id=_PLAYER2_ID),
        _make_player(2, ai_persona_id=1),
        _make_player(3, ai_persona_id=2),
    ]
    svc, _, _ = _make_service(room=room, players=players)

    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    assert len(snapshot["players"]) == 4
    ai_players = [p for p in snapshot["players"] if p["is_ai"]]
    assert len(ai_players) == 2
    human_players = [p for p in snapshot["players"] if not p["is_ai"]]
    assert len(human_players) == 2


@pytest.mark.asyncio
async def test_snapshot_contains_sixteen_pawns_for_four_player_game() -> None:
    """All 16 pawns (4 per player) must be present in a 4-player game."""
    room = _make_room()
    players = [_make_player(i, user_id=_HOST_ID if i == 0 else None, ai_persona_id=None if i == 0 else i)
               for i in range(4)]
    players[0] = _make_player(0, user_id=_HOST_ID)
    players[1] = _make_player(1, user_id=_PLAYER2_ID)
    players[2] = _make_player(2, ai_persona_id=1)
    players[3] = _make_player(3, ai_persona_id=2)
    svc, _, _ = _make_service(room=room, players=players)

    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    assert len(snapshot["pawns"]) == 4 * PAWNS_PER_PLAYER  # 16


# ---------------------------------------------------------------------------
# Pawn initialisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pawns_are_placed_at_home_positions() -> None:
    """Every pawn in the snapshot must start at its color's home position."""
    room = _make_room()
    players = [
        _make_player(0, user_id=_HOST_ID),
        _make_player(1, user_id=_PLAYER2_ID),
    ]
    svc, _, _ = _make_service(room=room, players=players)

    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    assert len(snapshot["pawns"]) == 2 * PAWNS_PER_PLAYER
    for pawn in snapshot["pawns"]:
        color = pawn["color"]
        expected = list(HOME_POSITIONS[color])
        assert pawn["position"] == expected, (
            f"pawn_id={pawn['pawn_id']} color={color}: "
            f"expected {expected}, got {pawn['position']}"
        )
        assert pawn["is_home"] is True
        assert pawn["is_finished"] is False


@pytest.mark.asyncio
async def test_each_player_has_exactly_four_pawns() -> None:
    svc, _, _ = _two_player_setup()
    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    pawns_by_player: dict[int, list[dict]] = {}
    for pawn in snapshot["pawns"]:
        idx = pawn["player_index"]
        pawns_by_player.setdefault(idx, []).append(pawn)

    for idx, pawns in pawns_by_player.items():
        assert len(pawns) == PAWNS_PER_PLAYER, (
            f"Player {idx} has {len(pawns)} pawns, expected {PAWNS_PER_PLAYER}"
        )


# ---------------------------------------------------------------------------
# Room status update
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_room_status_update_called_with_started_at_timestamp() -> None:
    svc, mock_repo, _ = _two_player_setup()
    await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    mock_repo.update_room_started.assert_awaited_once()
    args = mock_repo.update_room_started.call_args.args
    assert args[0] == _ROOM_ID, "Should pass the room UUID"
    assert isinstance(args[1], datetime), "Should pass a datetime for started_at"


# ---------------------------------------------------------------------------
# Game state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_game_state_is_rolling_after_start() -> None:
    svc, _, _ = _two_player_setup()
    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)
    assert snapshot["state"] == "ROLLING"


@pytest.mark.asyncio
async def test_first_player_index_is_zero() -> None:
    svc, _, _ = _two_player_setup()
    snapshot = await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)
    assert snapshot["current_player_index"] == 0


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_audit_log_entry_created_with_game_started_action() -> None:
    svc, mock_repo, _ = _two_player_setup()
    await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    mock_repo.create_audit_log.assert_awaited_once()
    kwargs = mock_repo.create_audit_log.call_args.kwargs
    assert kwargs["action"] == "game.started"
    assert kwargs["entity_type"] == "room"
    assert kwargs["entity_id"] == str(_ROOM_ID)
    assert kwargs["actor_id"] == _HOST_ID


@pytest.mark.asyncio
async def test_audit_log_metadata_contains_player_count() -> None:
    svc, mock_repo, _ = _two_player_setup()
    await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    kwargs = mock_repo.create_audit_log.call_args.kwargs
    metadata = kwargs["metadata"]
    assert metadata["player_count"] == 2
    assert metadata["room_code"] == _ROOM_CODE


# ---------------------------------------------------------------------------
# Redis persistence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_game_session_stored_in_redis_keyed_by_room_id() -> None:
    svc, _, mock_redis = _two_player_setup()
    await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    mock_redis.set.assert_awaited_once()
    key, value = mock_redis.set.call_args.args[:2]
    assert str(_ROOM_ID) in key, f"Redis key should contain room ID; got: {key}"
    # Value should be valid JSON containing the session state.
    import json
    parsed = json.loads(value)
    assert parsed["state"] == "ROLLING"
    assert parsed["room_id"] == str(_ROOM_ID)


@pytest.mark.asyncio
async def test_redis_set_called_with_ttl() -> None:
    svc, _, mock_redis = _two_player_setup()
    await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    kwargs = mock_redis.set.call_args.kwargs
    assert "ex" in kwargs, "Redis set should be called with an 'ex' TTL keyword arg"
    assert isinstance(kwargs["ex"], int)
    assert kwargs["ex"] > 0


# ---------------------------------------------------------------------------
# Error conditions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_with_one_player_raises_400() -> None:
    room = _make_room()
    players = [_make_player(0, user_id=_HOST_ID)]
    svc, _, _ = _make_service(room=room, players=players)

    with pytest.raises(GameStartError) as exc_info:
        await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    assert exc_info.value.http_status == 400
    assert "2 players" in str(exc_info.value)


@pytest.mark.asyncio
async def test_start_with_zero_players_raises_400() -> None:
    room = _make_room()
    svc, _, _ = _make_service(room=room, players=[])

    with pytest.raises(GameStartError) as exc_info:
        await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    assert exc_info.value.http_status == 400


@pytest.mark.asyncio
async def test_non_host_cannot_start_raises_403() -> None:
    room = _make_room()
    players = [
        _make_player(0, user_id=_HOST_ID),
        _make_player(1, user_id=_PLAYER2_ID),
    ]
    svc, _, _ = _make_service(room=room, players=players)

    with pytest.raises(GameStartError) as exc_info:
        await svc.start_game(room_code=_ROOM_CODE, requester_id="not-the-host")

    assert exc_info.value.http_status == 403
    assert "host" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_already_started_game_raises_409() -> None:
    room = _make_room(status=RoomStatus.PLAYING.value)
    players = [
        _make_player(0, user_id=_HOST_ID),
        _make_player(1, user_id=_PLAYER2_ID),
    ]
    svc, _, _ = _make_service(room=room, players=players)

    with pytest.raises(GameStartError) as exc_info:
        await svc.start_game(room_code=_ROOM_CODE, requester_id=_HOST_ID)

    assert exc_info.value.http_status == 409


@pytest.mark.asyncio
async def test_room_not_found_raises_404() -> None:
    svc, _, _ = _make_service(room=None, players=[])

    with pytest.raises(GameStartError) as exc_info:
        await svc.start_game(room_code="ZZZZZZ", requester_id=_HOST_ID)

    assert exc_info.value.http_status == 404


@pytest.mark.asyncio
async def test_db_not_mutated_when_room_not_found() -> None:
    """Repository update methods must not be called if the room is absent."""
    svc, mock_repo, mock_redis = _make_service(room=None, players=[])

    with pytest.raises(GameStartError):
        await svc.start_game(room_code="ZZZZZZ", requester_id=_HOST_ID)

    mock_repo.update_room_started.assert_not_awaited()
    mock_repo.create_audit_log.assert_not_awaited()
    mock_redis.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_db_not_mutated_when_requester_is_not_host() -> None:
    """No side effects should occur when auth check fails."""
    room = _make_room()
    players = [
        _make_player(0, user_id=_HOST_ID),
        _make_player(1, user_id=_PLAYER2_ID),
    ]
    svc, mock_repo, mock_redis = _make_service(room=room, players=players)

    with pytest.raises(GameStartError):
        await svc.start_game(room_code=_ROOM_CODE, requester_id="intruder")

    mock_repo.update_room_started.assert_not_awaited()
    mock_repo.create_audit_log.assert_not_awaited()
    mock_redis.set.assert_not_awaited()
