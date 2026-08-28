"""Tests for the WebSocket endpoint and related helpers.

Tests cover all acceptance criteria:
  AC-1  Valid JWT accepted; invalid/missing JWT rejected with code 4001.
  AC-2  roll_request triggers roll and broadcasts roll_result.
  AC-3  select_pawn triggers move and broadcasts game_state_update.
  AC-4  Non-current-player action rejected with "Not your turn".
  AC-5  Redis pub/sub publish called on game actions (fan-out wiring).
  AC-6  Reconnecting client receives full state_update.
  AC-7  Disconnected player marked in Redis with TTL; connection cleaned up.
  AC-8  Audit logs written for game.roll and game.move.

All external dependencies (Redis, GameSession, ws_authenticate) are mocked
so tests run without any infrastructure.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.websocket import (
    MAX_MESSAGE_BYTES,
    ErrorMessage,
    GameStateUpdateMessage,
    PongMessage,
    RollResultMessage,
    StateUpdateMessage,
    parse_client_message,
)
from app.services.connection_manager import ConnectionManager


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_ws() -> MagicMock:
    """Mock WebSocket with awaitable ``accept``, ``send_json``, ``close``."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


def _make_redis(current_player: str | None = None) -> MagicMock:
    """Mock Redis with the commands used by the WebSocket handler."""
    redis = MagicMock()
    redis.exists = AsyncMock(return_value=0)
    redis.delete = AsyncMock()
    redis.get = AsyncMock(return_value=current_player)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.publish = AsyncMock()

    # pubsub stub — listen() yields nothing by default
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.unsubscribe = AsyncMock()
    pubsub.aclose = AsyncMock()

    async def _empty_listen():
        # Default: just wait until cancelled
        await asyncio.sleep(3600)
        return
        yield  # make it an async generator

    pubsub.listen = _empty_listen
    redis.pubsub = MagicMock(return_value=pubsub)
    return redis


def _make_game_session(
    roll_result: dict | None = None,
    state_delta: dict | None = None,
    current_player: str | None = None,
    state: dict | None = None,
) -> MagicMock:
    gs = MagicMock()
    gs.get_current_player = AsyncMock(return_value=current_player)
    gs.get_state = AsyncMock(return_value=state or {"phase": "rolling", "board": {}})
    gs.roll = AsyncMock(
        return_value=roll_result or {"value": 4, "shells": [True, True, True, True], "player_id": "p1"}
    )
    gs.select_pawn = AsyncMock(
        return_value=state_delta or {"last_move": {"player_id": "p1", "pawn_id": 0}, "phase": "rolling"}
    )
    return gs


# ---------------------------------------------------------------------------
# Schema / parse_client_message tests
# ---------------------------------------------------------------------------


def test_parse_roll_request() -> None:
    msg = parse_client_message({"type": "roll_request"})
    assert msg.type == "roll_request"


def test_parse_select_pawn() -> None:
    msg = parse_client_message({"type": "select_pawn", "pawn_id": 2})
    assert msg.type == "select_pawn"
    assert msg.pawn_id == 2  # type: ignore[union-attr]


def test_parse_ping() -> None:
    msg = parse_client_message({"type": "ping"})
    assert msg.type == "ping"


def test_parse_unknown_type_raises() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        parse_client_message({"type": "chat", "text": "hello"})


def test_select_pawn_id_bounds() -> None:
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        parse_client_message({"type": "select_pawn", "pawn_id": -1})

    with pytest.raises(pydantic.ValidationError):
        parse_client_message({"type": "select_pawn", "pawn_id": 16})


# ---------------------------------------------------------------------------
# ws_authenticate tests
# ---------------------------------------------------------------------------


def test_ws_authenticate_missing_token_raises() -> None:
    from fastapi import WebSocketException

    from app.dependencies.auth import ws_authenticate

    with pytest.raises(WebSocketException) as exc_info:
        ws_authenticate("")
    assert exc_info.value.code == 4001


def test_ws_authenticate_invalid_token_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    from fastapi import WebSocketException

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    from app.dependencies.auth import ws_authenticate

    with pytest.raises(WebSocketException) as exc_info:
        ws_authenticate("not.a.real.token")
    assert exc_info.value.code == 4001


def test_ws_authenticate_valid_token_returns_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    import jwt

    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("JWT_ALGORITHM", "HS256")

    token = jwt.encode({"sub": "user_abc", "room": "r1"}, "test-secret", algorithm="HS256")

    from app.dependencies.auth import ws_authenticate

    claims = ws_authenticate(token)
    assert claims["sub"] == "user_abc"


def test_ws_authenticate_no_secret_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import WebSocketException

    monkeypatch.delenv("JWT_SECRET", raising=False)

    from app.dependencies.auth import ws_authenticate

    with pytest.raises(WebSocketException) as exc_info:
        ws_authenticate("some.token.here")
    assert exc_info.value.code == 4001


# ---------------------------------------------------------------------------
# _dispatch helper tests (unit-level, no real WebSocket)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatch_ping_returns_pong() -> None:
    from app.routes.websocket import _dispatch
    from app.schemas.websocket import PingMessage

    ws = _make_ws()
    gs = _make_game_session()
    redis = _make_redis()

    await _dispatch(
        msg=PingMessage(),
        room_id="r1",
        player_id="p1",
        websocket=ws,
        game_session=gs,
        redis=redis,
    )

    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "pong"


@pytest.mark.asyncio
async def test_dispatch_rejects_out_of_turn_action() -> None:
    from app.routes.websocket import _dispatch
    from app.schemas.websocket import RollRequestMessage

    ws = _make_ws()
    gs = _make_game_session(current_player="p2")  # it's p2's turn
    redis = _make_redis()

    await _dispatch(
        msg=RollRequestMessage(),
        room_id="r1",
        player_id="p1",  # wrong player
        websocket=ws,
        game_session=gs,
        redis=redis,
    )

    ws.send_json.assert_awaited_once()
    sent = ws.send_json.call_args[0][0]
    assert sent["type"] == "error"
    assert "Not your turn" in sent["message"]


@pytest.mark.asyncio
async def test_dispatch_roll_request_publishes_to_redis() -> None:
    """AC-2 and AC-5: roll_request triggers roll and publishes to Redis."""
    from app.routes.websocket import _dispatch
    from app.schemas.websocket import RollRequestMessage

    ws = _make_ws()
    redis = _make_redis()
    gs = _make_game_session(
        current_player=None,  # game not started — allow any player
        roll_result={"value": 4, "shells": [True, True, True, True], "player_id": "p1"},
    )

    with patch("app.routes.websocket.write_audit_log", new=AsyncMock()):
        await _dispatch(
            msg=RollRequestMessage(),
            room_id="r1",
            player_id="p1",
            websocket=ws,
            game_session=gs,
            redis=redis,
        )

    # Redis publish must have been called on the correct channel
    redis.publish.assert_awaited_once()
    channel, payload = redis.publish.call_args[0]
    assert channel == "room:r1"
    data = json.loads(payload)
    assert data["type"] == "roll_result"
    assert data["value"] == 4
    assert data["player_id"] == "p1"


@pytest.mark.asyncio
async def test_dispatch_select_pawn_publishes_state_update() -> None:
    """AC-3 and AC-5: select_pawn triggers move and publishes game_state_update."""
    from app.routes.websocket import _dispatch
    from app.schemas.websocket import SelectPawnMessage

    ws = _make_ws()
    redis = _make_redis()
    gs = _make_game_session(
        current_player=None,
        state_delta={"last_move": {"player_id": "p1", "pawn_id": 2}, "phase": "rolling"},
    )

    with patch("app.routes.websocket.write_audit_log", new=AsyncMock()):
        await _dispatch(
            msg=SelectPawnMessage(pawn_id=2),
            room_id="r1",
            player_id="p1",
            websocket=ws,
            game_session=gs,
            redis=redis,
        )

    redis.publish.assert_awaited_once()
    channel, payload = redis.publish.call_args[0]
    assert channel == "room:r1"
    data = json.loads(payload)
    assert data["type"] == "game_state_update"
    assert data["state_delta"]["last_move"]["pawn_id"] == 2


@pytest.mark.asyncio
async def test_dispatch_roll_writes_audit_log() -> None:
    """AC-8: game.roll action is written to the audit log."""
    from app.routes.websocket import _dispatch
    from app.schemas.websocket import RollRequestMessage

    ws = _make_ws()
    redis = _make_redis()
    gs = _make_game_session(current_player=None)

    with patch("app.routes.websocket.write_audit_log", new=AsyncMock()) as mock_audit:
        await _dispatch(
            msg=RollRequestMessage(),
            room_id="r1",
            player_id="p1",
            websocket=ws,
            game_session=gs,
            redis=redis,
        )

    mock_audit.assert_awaited_once()
    call_kwargs = mock_audit.call_args
    assert call_kwargs.kwargs["action"] == "game.roll"


@pytest.mark.asyncio
async def test_dispatch_move_writes_audit_log() -> None:
    """AC-8: game.move action is written to the audit log."""
    from app.routes.websocket import _dispatch
    from app.schemas.websocket import SelectPawnMessage

    ws = _make_ws()
    redis = _make_redis()
    gs = _make_game_session(current_player=None)

    with patch("app.routes.websocket.write_audit_log", new=AsyncMock()) as mock_audit:
        await _dispatch(
            msg=SelectPawnMessage(pawn_id=1),
            room_id="r1",
            player_id="p1",
            websocket=ws,
            game_session=gs,
            redis=redis,
        )

    mock_audit.assert_awaited_once()
    call_kwargs = mock_audit.call_args
    assert call_kwargs.kwargs["action"] == "game.move"


# ---------------------------------------------------------------------------
# websocket_endpoint integration-style tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_endpoint_rejects_missing_token() -> None:
    """AC-1: missing token causes websocket.close(code=4001)."""
    from fastapi import WebSocketException

    from app.routes.websocket import websocket_endpoint

    ws = _make_ws()

    with patch(
        "app.routes.websocket.ws_authenticate",
        side_effect=WebSocketException(code=4001, reason="Missing token"),
    ):
        await websocket_endpoint(websocket=ws, room_id="r1", token="")

    ws.close.assert_awaited_once_with(code=4001)
    ws.accept.assert_not_called()


@pytest.mark.asyncio
async def test_endpoint_rejects_invalid_token() -> None:
    """AC-1: invalid token causes websocket.close(code=4001)."""
    from fastapi import WebSocketException

    from app.routes.websocket import websocket_endpoint

    ws = _make_ws()

    with patch(
        "app.routes.websocket.ws_authenticate",
        side_effect=WebSocketException(code=4001, reason="Invalid token"),
    ):
        await websocket_endpoint(websocket=ws, room_id="r1", token="bad.token")

    ws.close.assert_awaited_once_with(code=4001)


@pytest.mark.asyncio
async def test_endpoint_accepts_valid_token_and_disconnects_cleanly() -> None:
    """AC-1: valid JWT → accept; AC-7: disconnect marks player in Redis."""
    from fastapi import WebSocketDisconnect

    from app.routes.websocket import websocket_endpoint

    ws = _make_ws()
    redis = _make_redis()
    gs = _make_game_session()

    # Simulate immediate disconnect after accepting
    ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    with (
        patch("app.routes.websocket.ws_authenticate", return_value={"sub": "p1"}),
        patch("app.routes.websocket.get_redis", new=AsyncMock(return_value=redis)),
        patch("app.routes.websocket.GameSession", return_value=gs),
        patch("app.routes.websocket._redis_pubsub_listener", new=AsyncMock()),
        patch("app.services.connection_manager.manager.register"),
        patch("app.services.connection_manager.manager.deregister"),
    ):
        await websocket_endpoint(websocket=ws, room_id="r1", token="valid.token")

    ws.accept.assert_awaited_once()
    # AC-7: disconnected key set with TTL
    redis.setex.assert_awaited_once()
    key_arg = redis.setex.call_args[0][0]
    ttl_arg = redis.setex.call_args[0][1]
    assert "r1" in key_arg
    assert "p1" in key_arg
    assert ttl_arg == 60


@pytest.mark.asyncio
async def test_endpoint_sends_full_state_on_reconnect() -> None:
    """AC-6: reconnecting client receives full state_update immediately."""
    from fastapi import WebSocketDisconnect

    from app.routes.websocket import websocket_endpoint

    ws = _make_ws()
    redis = _make_redis()
    redis.exists = AsyncMock(return_value=1)  # disconnection record exists
    gs = _make_game_session(state={"phase": "rolling", "board": {"pos": 5}})

    ws.receive_text = AsyncMock(side_effect=WebSocketDisconnect())

    with (
        patch("app.routes.websocket.ws_authenticate", return_value={"sub": "p1"}),
        patch("app.routes.websocket.get_redis", new=AsyncMock(return_value=redis)),
        patch("app.routes.websocket.GameSession", return_value=gs),
        patch("app.routes.websocket._redis_pubsub_listener", new=AsyncMock()),
        patch("app.services.connection_manager.manager.register"),
        patch("app.services.connection_manager.manager.deregister"),
    ):
        await websocket_endpoint(websocket=ws, room_id="r1", token="valid.token")

    # Full state message sent
    sent_calls = ws.send_json.call_args_list
    assert len(sent_calls) >= 1
    first_msg = sent_calls[0][0][0]
    assert first_msg["type"] == "state_update"
    assert first_msg["state"]["board"]["pos"] == 5


@pytest.mark.asyncio
async def test_endpoint_rejects_oversized_message() -> None:
    """Messages > 1 KB are rejected with an error, not processed."""
    from fastapi import WebSocketDisconnect

    from app.routes.websocket import websocket_endpoint

    ws = _make_ws()
    redis = _make_redis()
    gs = _make_game_session()

    oversized = "x" * (MAX_MESSAGE_BYTES + 1)
    # Return oversized message first, then disconnect
    ws.receive_text = AsyncMock(side_effect=[oversized, WebSocketDisconnect()])

    with (
        patch("app.routes.websocket.ws_authenticate", return_value={"sub": "p1"}),
        patch("app.routes.websocket.get_redis", new=AsyncMock(return_value=redis)),
        patch("app.routes.websocket.GameSession", return_value=gs),
        patch("app.routes.websocket._redis_pubsub_listener", new=AsyncMock()),
        patch("app.services.connection_manager.manager.register"),
        patch("app.services.connection_manager.manager.deregister"),
    ):
        await websocket_endpoint(websocket=ws, room_id="r1", token="valid.token")

    error_calls = [
        call
        for call in ws.send_json.call_args_list
        if call[0][0].get("type") == "error"
    ]
    assert len(error_calls) >= 1
    assert "size" in error_calls[0][0][0]["message"].lower()


# ---------------------------------------------------------------------------
# GameSession unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_game_session_roll_returns_valid_result() -> None:
    from app.services.game_session import GameSession, _COWRIE_VALUE_TABLE

    redis = _make_redis()
    redis.get = AsyncMock(return_value=None)
    gs = GameSession(room_id="r1", redis=redis)

    result = await gs.roll("p1")

    assert "value" in result
    assert "shells" in result
    assert result["player_id"] == "p1"
    assert len(result["shells"]) == 4
    assert result["value"] in _COWRIE_VALUE_TABLE.values()


@pytest.mark.asyncio
async def test_game_session_select_pawn_returns_delta() -> None:
    from app.services.game_session import GameSession

    redis = _make_redis()
    redis.get = AsyncMock(return_value=json.dumps({"phase": "selecting"}))
    gs = GameSession(room_id="r1", redis=redis)

    delta = await gs.select_pawn("p1", 3)

    assert "last_move" in delta
    assert delta["last_move"]["pawn_id"] == 3
    assert delta["phase"] == "rolling"


@pytest.mark.asyncio
async def test_game_session_get_state_returns_empty_dict_when_no_state() -> None:
    from app.services.game_session import GameSession

    redis = _make_redis()
    redis.get = AsyncMock(return_value=None)
    gs = GameSession(room_id="r1", redis=redis)

    state = await gs.get_state()
    assert state == {}
