"""Unit tests for the ConnectionManager service.

Tests cover: registration, deregistration, querying, and broadcasting.
WebSocket objects are replaced with lightweight mocks so no real network
connections are required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.connection_manager import ConnectionManager


@pytest.fixture()
def manager() -> ConnectionManager:
    """Fresh ConnectionManager instance for each test."""
    return ConnectionManager()


def _make_ws() -> MagicMock:
    """Return a mock WebSocket with a stub ``send_json`` coroutine."""
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# Registration / deregistration
# ---------------------------------------------------------------------------


def test_register_adds_connection(manager: ConnectionManager) -> None:
    ws = _make_ws()
    manager.register("room1", "player1", ws)
    assert "player1" in manager.get_player_ids("room1")


def test_register_multiple_players_in_room(manager: ConnectionManager) -> None:
    ws1, ws2 = _make_ws(), _make_ws()
    manager.register("room1", "player1", ws1)
    manager.register("room1", "player2", ws2)
    ids = manager.get_player_ids("room1")
    assert "player1" in ids
    assert "player2" in ids


def test_deregister_removes_connection(manager: ConnectionManager) -> None:
    ws = _make_ws()
    manager.register("room1", "player1", ws)
    manager.deregister("room1", "player1", ws)
    assert manager.get_player_ids("room1") == []


def test_deregister_cleans_empty_room(manager: ConnectionManager) -> None:
    """Room key is removed when the last connection deregisters."""
    ws = _make_ws()
    manager.register("room1", "player1", ws)
    manager.deregister("room1", "player1", ws)
    # Should not raise; room entry is gone
    assert manager.connection_count("room1") == 0


def test_deregister_nonexistent_room_is_safe(manager: ConnectionManager) -> None:
    ws = _make_ws()
    # Must not raise
    manager.deregister("ghost-room", "player1", ws)


def test_deregister_by_websocket_identity(manager: ConnectionManager) -> None:
    """Only the matching websocket object is removed, not all for the player."""
    ws1 = _make_ws()
    ws2 = _make_ws()
    manager.register("room1", "player1", ws1)
    manager.register("room1", "player1", ws2)  # duplicate player, two ws objects
    manager.deregister("room1", "player1", ws1)
    # ws2 still registered
    assert manager.connection_count("room1") == 1


def test_connection_count(manager: ConnectionManager) -> None:
    ws1, ws2 = _make_ws(), _make_ws()
    assert manager.connection_count("room1") == 0
    manager.register("room1", "player1", ws1)
    assert manager.connection_count("room1") == 1
    manager.register("room1", "player2", ws2)
    assert manager.connection_count("room1") == 2


# ---------------------------------------------------------------------------
# Messaging
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_to_player_delivers_message(manager: ConnectionManager) -> None:
    ws = _make_ws()
    manager.register("room1", "player1", ws)
    await manager.send_to_player("room1", "player1", {"type": "pong"})
    ws.send_json.assert_awaited_once_with({"type": "pong"})


@pytest.mark.asyncio
async def test_send_to_player_unknown_player_silent(manager: ConnectionManager) -> None:
    """No error raised when player is not connected."""
    await manager.send_to_player("room1", "ghost", {"type": "pong"})  # no-op


@pytest.mark.asyncio
async def test_broadcast_delivers_to_all_connections(manager: ConnectionManager) -> None:
    ws1, ws2 = _make_ws(), _make_ws()
    manager.register("room1", "player1", ws1)
    manager.register("room1", "player2", ws2)

    msg = {"type": "roll_result", "value": 4}
    await manager.broadcast_to_room("room1", msg)

    ws1.send_json.assert_awaited_once_with(msg)
    ws2.send_json.assert_awaited_once_with(msg)


@pytest.mark.asyncio
async def test_broadcast_empty_room_is_safe(manager: ConnectionManager) -> None:
    """Broadcasting to a room with no connections must not raise."""
    await manager.broadcast_to_room("empty-room", {"type": "ping"})


@pytest.mark.asyncio
async def test_broadcast_continues_after_single_failure(manager: ConnectionManager) -> None:
    """One failing send must not prevent others from receiving the message."""
    ws1, ws2 = _make_ws(), _make_ws()
    ws1.send_json.side_effect = RuntimeError("connection lost")
    manager.register("room1", "player1", ws1)
    manager.register("room1", "player2", ws2)

    await manager.broadcast_to_room("room1", {"type": "pong"})

    # ws2 must still receive the message despite ws1 failing.
    ws2.send_json.assert_awaited_once_with({"type": "pong"})
