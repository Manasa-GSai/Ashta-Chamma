"""Tests for spectator mode (WO-026).

Coverage:
  - Spectator join flow via POST /api/rooms/{code}/spectate
  - Spectator receives all game state updates via WebSocket
  - Spectator cannot send roll_request (rejected with error)
  - Spectator cannot send select_pawn (rejected with error)
  - Spectator can send chat messages
  - Spectators do not count toward max_players
  - Players (non-spectators) can send game actions normally
"""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.routes import websocket as ws_module
from app.services import room_service


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Reset all in-memory state before each test to ensure isolation."""
    room_service.clear_all()
    ws_module.clear_connections()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def room_code(client: TestClient) -> str:
    """Create a room and return its 6-character code."""
    resp = client.post("/api/rooms", headers={"x-user-id": "host-001"})
    assert resp.status_code == 200
    return str(resp.json()["code"])


# ---------------------------------------------------------------------------
# REST endpoint tests
# ---------------------------------------------------------------------------


class TestSpectateEndpoint:
    def test_spectator_can_join_room(self, client: TestClient, room_code: str) -> None:
        """AC-1: A user can join a room as a spectator via POST /spectate."""
        resp = client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "spec-001", "x-display-name": "Watcher"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["room_code"] == room_code
        assert body["user_id"] == "spec-001"
        assert "spectating" in body["message"].lower()

    def test_spectate_unknown_room_returns_404(self, client: TestClient) -> None:
        """Spectating a nonexistent room returns 404."""
        resp = client.post(
            "/api/rooms/XXXXXX/spectate",
            headers={"x-user-id": "spec-001"},
        )
        assert resp.status_code == 404

    def test_spectate_requires_user_id_header(
        self, client: TestClient, room_code: str
    ) -> None:
        """Missing X-User-Id header returns 401."""
        resp = client.post(f"/api/rooms/{room_code}/spectate")
        assert resp.status_code == 401

    def test_player_cannot_spectate_own_room(
        self, client: TestClient, room_code: str
    ) -> None:
        """A user who joined as a player cannot also spectate the same room."""
        client.post(
            f"/api/rooms/{room_code}/join",
            headers={"x-user-id": "player-001", "x-display-name": "Player"},
        )
        resp = client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "player-001"},
        )
        assert resp.status_code == 409

    def test_spectator_does_not_count_toward_max_players(
        self, client: TestClient
    ) -> None:
        """AC-6: Spectators do not count toward max_players."""
        # Create a room (default max 4 players)
        resp = client.post("/api/rooms", headers={"x-user-id": "host-001"})
        code: str = resp.json()["code"]

        # Fill all player slots
        for i in range(4):
            join_resp = client.post(
                f"/api/rooms/{code}/join",
                headers={"x-user-id": f"player-{i}", "x-display-name": f"P{i}"},
            )
            assert join_resp.status_code == 200

        # A fifth user cannot join as a player
        assert (
            client.post(
                f"/api/rooms/{code}/join",
                headers={"x-user-id": "player-extra"},
            ).status_code
            == 409
        )

        # But they can join as a spectator
        spec_resp = client.post(
            f"/api/rooms/{code}/spectate",
            headers={"x-user-id": "spec-001"},
        )
        assert spec_resp.status_code == 200

    def test_spectate_idempotent(self, client: TestClient, room_code: str) -> None:
        """Calling spectate twice for the same user is idempotent."""
        headers = {"x-user-id": "spec-001"}
        assert client.post(f"/api/rooms/{room_code}/spectate", headers=headers).status_code == 200
        assert client.post(f"/api/rooms/{room_code}/spectate", headers=headers).status_code == 200


# ---------------------------------------------------------------------------
# WebSocket tests
# ---------------------------------------------------------------------------


class TestSpectatorWebSocket:
    def test_spectator_receives_initial_state_update(
        self, client: TestClient, room_code: str
    ) -> None:
        """AC-2: Spectators receive game state updates via WebSocket."""
        client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "spec-001"},
        )
        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=spec-001&display_name=Watcher"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "state_update"
            assert data["is_spectator"] is True

    def test_spectator_cannot_send_roll_request(
        self, client: TestClient, room_code: str
    ) -> None:
        """AC-3: Spectators receive an error when sending roll_request."""
        client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "spec-001"},
        )
        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=spec-001"
        ) as ws:
            ws.receive_json()  # consume state_update

            ws.send_json({"type": "roll_request"})
            error = ws.receive_json()

            assert error["type"] == "error"
            assert error["message"] == "Spectators cannot perform game actions"

    def test_spectator_cannot_send_select_pawn(
        self, client: TestClient, room_code: str
    ) -> None:
        """AC-3: Spectators receive an error when sending select_pawn."""
        client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "spec-001"},
        )
        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=spec-001"
        ) as ws:
            ws.receive_json()  # consume state_update

            ws.send_json({"type": "select_pawn", "pawn_id": 0})
            error = ws.receive_json()

            assert error["type"] == "error"
            assert error["message"] == "Spectators cannot perform game actions"

    def test_spectator_can_send_chat(
        self, client: TestClient, room_code: str
    ) -> None:
        """AC-4: Spectators can send chat messages."""
        client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "spec-001", "x-display-name": "Watcher"},
        )
        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=spec-001&display_name=Watcher"
        ) as ws:
            ws.receive_json()  # consume state_update

            ws.send_json({"type": "chat", "text": "Go team!"})
            chat = ws.receive_json()

            assert chat["type"] == "chat"
            assert chat["text"] == "Go team!"
            assert chat["from"] == "Watcher"

    def test_player_can_send_roll_request(
        self, client: TestClient, room_code: str
    ) -> None:
        """Players (non-spectators) can send roll_request without error."""
        client.post(
            f"/api/rooms/{room_code}/join",
            headers={"x-user-id": "player-001", "x-display-name": "Player"},
        )
        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=player-001&display_name=Player"
        ) as ws:
            ws.receive_json()  # consume state_update

            ws.send_json({"type": "roll_request"})
            response = ws.receive_json()

            # Response must not be an error
            assert response.get("type") != "error"

    def test_player_can_send_select_pawn(
        self, client: TestClient, room_code: str
    ) -> None:
        """Players can send select_pawn without error."""
        client.post(
            f"/api/rooms/{room_code}/join",
            headers={"x-user-id": "player-001", "x-display-name": "Player"},
        )
        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=player-001&display_name=Player"
        ) as ws:
            ws.receive_json()  # consume state_update

            ws.send_json({"type": "select_pawn", "pawn_id": 1})
            response = ws.receive_json()

            assert response.get("type") != "error"

    def test_websocket_rejects_unknown_room(self, client: TestClient) -> None:
        """WebSocket connection to an unknown room closes with 4004."""
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/ws/rooms/XXXXXX?user_id=spec-001"
            ) as ws:
                ws.receive_json()

    def test_spectator_receives_broadcast_from_player(
        self, client: TestClient, room_code: str
    ) -> None:
        """AC-2: Spectators receive state updates triggered by player actions."""
        client.post(
            f"/api/rooms/{room_code}/spectate",
            headers={"x-user-id": "spec-001"},
        )
        client.post(
            f"/api/rooms/{room_code}/join",
            headers={"x-user-id": "player-001", "x-display-name": "Player"},
        )

        with client.websocket_connect(
            f"/ws/rooms/{room_code}?user_id=spec-001"
        ) as spec_ws:
            spec_ws.receive_json()  # consume initial state_update for spectator

            with client.websocket_connect(
                f"/ws/rooms/{room_code}?user_id=player-001&display_name=Player"
            ) as player_ws:
                player_ws.receive_json()  # consume initial state_update for player

                # Player sends a roll — broadcast should reach spectator
                player_ws.send_json({"type": "roll_request"})

                # The broadcast goes to all connections, including the player
                player_update = player_ws.receive_json()
                assert player_update["type"] == "state_update"

                # Spectator also receives the broadcast
                spec_update = spec_ws.receive_json()
                assert spec_update["type"] == "state_update"
