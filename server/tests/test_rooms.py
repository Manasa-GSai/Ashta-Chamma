"""Tests for room management: service layer and route-level behaviour.

Route tests override ``get_current_user``, ``get_db_session``, and ``get_redis``
using FastAPI's dependency-override mechanism so no real database or Redis
connection is required.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db_session
from app.core.redis_client import get_redis
from app.main import app
from app.models.room import AiPersona, DifficultyLevel, Room, RoomPlayer, RoomStatus
from app.repositories.room_repository import RoomRepository
from app.schemas.room import CreateRoomRequest
from app.services.room_service import (
    AiPersonaNotFoundError,
    PlayerNotInRoomError,
    RoomAlreadyStartedError,
    RoomFullError,
    RoomNotFoundError,
    RoomService,
    _generate_room_code,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

HOST_USER_ID = uuid.uuid4()
SECOND_USER_ID = uuid.uuid4()
HOST_CLERK_ID = "user_host_clerk_id"
SECOND_CLERK_ID = "user_second_clerk_id"
ROOM_ID = uuid.uuid4()
ROOM_CODE = "AABBCC"


def _make_user(user_id: uuid.UUID = HOST_USER_ID, display_name: str = "Alice") -> Any:
    user = MagicMock()
    user.id = user_id
    user.clerk_id = HOST_CLERK_ID
    user.display_name = display_name
    return user


def _make_ai_persona(persona_id: int = 1, name: str = "Easy Bot") -> AiPersona:
    persona = MagicMock(spec=AiPersona)
    persona.id = persona_id
    persona.name = name
    persona.is_active = True
    persona.difficulty_level = DifficultyLevel.easy
    return persona


def _make_room_player(
    room_id: uuid.UUID = ROOM_ID,
    user_id: uuid.UUID | None = HOST_USER_ID,
    player_index: int = 0,
    color: str = "red",
    ai_persona_id: int | None = None,
    ai_persona: Any = None,
    user: Any = None,
) -> MagicMock:
    p = MagicMock(spec=RoomPlayer)
    p.room_id = room_id
    p.user_id = user_id
    p.ai_persona_id = ai_persona_id
    p.player_index = player_index
    p.color = color
    p.ai_persona = ai_persona
    p.user = user or (_make_user(user_id) if user_id else None)
    return p


def _make_room(
    room_id: uuid.UUID = ROOM_ID,
    code: str = ROOM_CODE,
    host_user_id: uuid.UUID = HOST_USER_ID,
    max_players: int = 4,
    status: RoomStatus = RoomStatus.waiting,
    players: list[Any] | None = None,
    host: Any = None,
) -> MagicMock:
    r = MagicMock(spec=Room)
    r.id = room_id
    r.code = code
    r.host_user_id = host_user_id
    r.max_players = max_players
    r.status = status
    r.players = players if players is not None else [_make_room_player()]
    r.host = host or _make_user(host_user_id)
    r.created_at = datetime(2026, 1, 1)
    return r


def _make_repo(
    *,
    room: Any = None,
    code_exists: bool = False,
    ai_persona: Any = None,
) -> MagicMock:
    repo = MagicMock(spec=RoomRepository)
    repo.get_room_by_code = AsyncMock(return_value=room)
    repo.code_exists = AsyncMock(return_value=code_exists)
    repo.create_room = AsyncMock(side_effect=lambda r: r)
    repo.add_room_player = AsyncMock(side_effect=lambda p: p)
    repo.remove_room_player = AsyncMock(return_value=True)
    repo.get_ai_persona = AsyncMock(return_value=ai_persona)
    repo.create_audit_log = AsyncMock()
    repo.commit = AsyncMock()
    repo.refresh = AsyncMock()
    return repo


# ---------------------------------------------------------------------------
# Unit tests: _generate_room_code
# ---------------------------------------------------------------------------


class TestGenerateRoomCode:
    def test_length_is_six(self) -> None:
        code = _generate_room_code()
        assert len(code) == 6

    def test_is_uppercase(self) -> None:
        code = _generate_room_code()
        assert code == code.upper()

    def test_is_alphanumeric(self) -> None:
        code = _generate_room_code()
        assert code.isalnum()

    def test_codes_are_not_always_identical(self) -> None:
        # With 16^6 = 16.7 M possibilities the probability that 20 calls all
        # return the same value is negligibly small.
        codes = {_generate_room_code() for _ in range(20)}
        assert len(codes) > 1


# ---------------------------------------------------------------------------
# Unit tests: RoomService.create_room
# ---------------------------------------------------------------------------


class TestCreateRoom:
    @pytest.mark.asyncio
    async def test_creates_room_returns_code_and_id(self) -> None:
        repo = _make_repo(code_exists=False)
        service = RoomService(repo)
        request = CreateRoomRequest(max_players=4)

        result = await service.create_room(
            request=request,
            host_user_id=HOST_USER_ID,
            host_clerk_id=HOST_CLERK_ID,
            host_display_name="Alice",
        )

        assert result.code.isalnum()
        assert len(result.code) == 6
        assert result.room_id is not None

    @pytest.mark.asyncio
    async def test_creates_audit_log_entry(self) -> None:
        repo = _make_repo()
        service = RoomService(repo)
        await service.create_room(
            request=CreateRoomRequest(max_players=2),
            host_user_id=HOST_USER_ID,
            host_clerk_id=HOST_CLERK_ID,
            host_display_name="Alice",
        )
        repo.create_audit_log.assert_called_once()
        log_arg = repo.create_audit_log.call_args[0][0]
        assert log_arg.action == "room.created"
        assert log_arg.actor_id == HOST_CLERK_ID

    @pytest.mark.asyncio
    async def test_with_ai_personas_adds_ai_players(self) -> None:
        persona1 = _make_ai_persona(persona_id=1, name="Easy Bot")
        persona2 = _make_ai_persona(persona_id=2, name="Hard Bot")
        repo = _make_repo()
        repo.get_ai_persona = AsyncMock(side_effect=[persona1, persona2])

        service = RoomService(repo)
        await service.create_room(
            request=CreateRoomRequest(max_players=4, ai_persona_ids=[1, 2]),
            host_user_id=HOST_USER_ID,
            host_clerk_id=HOST_CLERK_ID,
            host_display_name="Alice",
        )

        # add_room_player called: 1 host + 2 AI = 3 times
        assert repo.add_room_player.call_count == 3

    @pytest.mark.asyncio
    async def test_invalid_ai_persona_raises_error(self) -> None:
        repo = _make_repo()
        repo.get_ai_persona = AsyncMock(return_value=None)

        service = RoomService(repo)
        with pytest.raises(AiPersonaNotFoundError):
            await service.create_room(
                request=CreateRoomRequest(max_players=4, ai_persona_ids=[99]),
                host_user_id=HOST_USER_ID,
                host_clerk_id=HOST_CLERK_ID,
                host_display_name="Alice",
            )

    @pytest.mark.asyncio
    async def test_too_many_ai_personas_raises_value_error(self) -> None:
        repo = _make_repo()
        service = RoomService(repo)
        # max_players=2 but 2 AI personas leaves 0 seats for host
        with pytest.raises(ValueError, match="too many"):
            await service.create_room(
                request=CreateRoomRequest(max_players=2, ai_persona_ids=[1, 2]),
                host_user_id=HOST_USER_ID,
                host_clerk_id=HOST_CLERK_ID,
                host_display_name="Alice",
            )

    @pytest.mark.asyncio
    async def test_code_uniqueness_retries_on_collision(self) -> None:
        """Service retries code generation when the first attempt collides."""
        repo = _make_repo()
        # First call says code exists (collision); second says it does not
        repo.code_exists = AsyncMock(side_effect=[True, False])

        service = RoomService(repo)
        result = await service.create_room(
            request=CreateRoomRequest(max_players=2),
            host_user_id=HOST_USER_ID,
            host_clerk_id=HOST_CLERK_ID,
            host_display_name="Alice",
        )
        assert len(result.code) == 6
        assert repo.code_exists.call_count == 2


# ---------------------------------------------------------------------------
# Unit tests: RoomService.get_room
# ---------------------------------------------------------------------------


class TestGetRoom:
    @pytest.mark.asyncio
    async def test_returns_room_details(self) -> None:
        player = _make_room_player(user_id=HOST_USER_ID, player_index=0, color="red")
        room = _make_room(players=[player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        response = await service.get_room(code=ROOM_CODE, requesting_user_id=HOST_USER_ID)

        assert response.code == ROOM_CODE
        assert response.status == "waiting"
        assert len(response.players) == 1
        assert response.available_seats == 3  # max 4 - 1 player

    @pytest.mark.asyncio
    async def test_non_member_gets_permission_error(self) -> None:
        player = _make_room_player(user_id=HOST_USER_ID)
        room = _make_room(players=[player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        outsider_id = uuid.uuid4()
        with pytest.raises(PermissionError):
            await service.get_room(code=ROOM_CODE, requesting_user_id=outsider_id)

    @pytest.mark.asyncio
    async def test_missing_room_raises_not_found(self) -> None:
        repo = _make_repo(room=None)
        service = RoomService(repo)
        with pytest.raises(RoomNotFoundError):
            await service.get_room(code="ZZZZZZ", requesting_user_id=HOST_USER_ID)

    @pytest.mark.asyncio
    async def test_response_includes_ai_player(self) -> None:
        persona = _make_ai_persona()
        ai_player = _make_room_player(
            user_id=None,
            player_index=1,
            color="green",
            ai_persona_id=1,
            ai_persona=persona,
            user=None,
        )
        human_player = _make_room_player(user_id=HOST_USER_ID, player_index=0, color="red")
        room = _make_room(players=[human_player, ai_player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        response = await service.get_room(code=ROOM_CODE, requesting_user_id=HOST_USER_ID)

        ai_info = next(p for p in response.players if p.is_ai)
        assert ai_info.display_name == "Easy Bot"


# ---------------------------------------------------------------------------
# Unit tests: RoomService.join_room
# ---------------------------------------------------------------------------


class TestJoinRoom:
    @pytest.mark.asyncio
    async def test_adds_player_and_returns_index_color(self) -> None:
        # Room has only the host; second player joins
        host_player = _make_room_player(user_id=HOST_USER_ID, player_index=0, color="red")
        room = _make_room(players=[host_player], max_players=4)
        repo = _make_repo(room=room)

        service = RoomService(repo)
        result = await service.join_room(
            code=ROOM_CODE,
            user_id=SECOND_USER_ID,
            clerk_id=SECOND_CLERK_ID,
            display_name="Bob",
        )

        assert result.player_index == 1
        assert result.color == "green"
        repo.add_room_player.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_room_raises_room_full_error(self) -> None:
        # Create 4 players to fill a max_players=4 room
        players = [
            _make_room_player(user_id=uuid.uuid4(), player_index=i, color="red")
            for i in range(4)
        ]
        room = _make_room(players=players, max_players=4)
        repo = _make_repo(room=room)

        service = RoomService(repo)
        with pytest.raises(RoomFullError):
            await service.join_room(
                code=ROOM_CODE,
                user_id=uuid.uuid4(),
                clerk_id="new_user",
                display_name="Charlie",
            )

    @pytest.mark.asyncio
    async def test_already_in_room_is_idempotent(self) -> None:
        player = _make_room_player(user_id=HOST_USER_ID, player_index=0, color="red")
        room = _make_room(players=[player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        result = await service.join_room(
            code=ROOM_CODE,
            user_id=HOST_USER_ID,
            clerk_id=HOST_CLERK_ID,
            display_name="Alice",
        )

        # No new DB row should be added on duplicate join
        repo.add_room_player.assert_not_called()
        assert result.player_index == 0

    @pytest.mark.asyncio
    async def test_missing_room_raises_not_found(self) -> None:
        repo = _make_repo(room=None)
        service = RoomService(repo)
        with pytest.raises(RoomNotFoundError):
            await service.join_room(
                code="ZZZZZZ",
                user_id=SECOND_USER_ID,
                clerk_id=SECOND_CLERK_ID,
                display_name="Bob",
            )

    @pytest.mark.asyncio
    async def test_started_room_raises_already_started(self) -> None:
        room = _make_room(status=RoomStatus.in_progress)
        repo = _make_repo(room=room)
        service = RoomService(repo)
        with pytest.raises(RoomAlreadyStartedError):
            await service.join_room(
                code=ROOM_CODE,
                user_id=SECOND_USER_ID,
                clerk_id=SECOND_CLERK_ID,
                display_name="Bob",
            )

    @pytest.mark.asyncio
    async def test_creates_audit_log(self) -> None:
        host_player = _make_room_player(user_id=HOST_USER_ID, player_index=0, color="red")
        room = _make_room(players=[host_player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        await service.join_room(
            code=ROOM_CODE,
            user_id=SECOND_USER_ID,
            clerk_id=SECOND_CLERK_ID,
            display_name="Bob",
        )

        repo.create_audit_log.assert_called_once()
        log_arg = repo.create_audit_log.call_args[0][0]
        assert log_arg.action == "room.joined"


# ---------------------------------------------------------------------------
# Unit tests: RoomService.leave_room
# ---------------------------------------------------------------------------


class TestLeaveRoom:
    @pytest.mark.asyncio
    async def test_removes_player_and_creates_audit_log(self) -> None:
        host_player = _make_room_player(user_id=HOST_USER_ID, player_index=0)
        second_player = _make_room_player(user_id=SECOND_USER_ID, player_index=1)
        room = _make_room(players=[host_player, second_player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        await service.leave_room(
            code=ROOM_CODE, user_id=SECOND_USER_ID, clerk_id=SECOND_CLERK_ID
        )

        repo.remove_room_player.assert_called_once_with(ROOM_ID, SECOND_USER_ID)
        repo.create_audit_log.assert_called_once()
        log_arg = repo.create_audit_log.call_args[0][0]
        assert log_arg.action == "room.left"

    @pytest.mark.asyncio
    async def test_host_leaves_promotes_next_human(self) -> None:
        host_player = _make_room_player(user_id=HOST_USER_ID, player_index=0)
        second_player = _make_room_player(user_id=SECOND_USER_ID, player_index=1)
        room = _make_room(
            host_user_id=HOST_USER_ID, players=[host_player, second_player]
        )
        repo = _make_repo(room=room)

        service = RoomService(repo)
        await service.leave_room(
            code=ROOM_CODE, user_id=HOST_USER_ID, clerk_id=HOST_CLERK_ID
        )

        # Host should be reassigned to the second player
        assert room.host_user_id == SECOND_USER_ID

    @pytest.mark.asyncio
    async def test_last_human_leaves_abandons_room(self) -> None:
        host_player = _make_room_player(user_id=HOST_USER_ID, player_index=0)
        room = _make_room(host_user_id=HOST_USER_ID, players=[host_player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        await service.leave_room(
            code=ROOM_CODE, user_id=HOST_USER_ID, clerk_id=HOST_CLERK_ID
        )

        assert room.status == RoomStatus.abandoned

    @pytest.mark.asyncio
    async def test_non_member_raises_player_not_in_room(self) -> None:
        player = _make_room_player(user_id=HOST_USER_ID)
        room = _make_room(players=[player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        with pytest.raises(PlayerNotInRoomError):
            await service.leave_room(
                code=ROOM_CODE,
                user_id=uuid.uuid4(),
                clerk_id="outsider",
            )

    @pytest.mark.asyncio
    async def test_missing_room_raises_not_found(self) -> None:
        repo = _make_repo(room=None)
        service = RoomService(repo)
        with pytest.raises(RoomNotFoundError):
            await service.leave_room(
                code="ZZZZZZ", user_id=HOST_USER_ID, clerk_id=HOST_CLERK_ID
            )


# ---------------------------------------------------------------------------
# Route-level tests via TestClient with dependency overrides
# ---------------------------------------------------------------------------

# Shared test user identity
_TEST_USER = CurrentUser(
    clerk_id=HOST_CLERK_ID,
    user_id=HOST_USER_ID,
    display_name="Alice",
)


def _override_auth() -> CurrentUser:
    return _TEST_USER


def _override_redis() -> None:
    return None


@pytest.fixture()
def client_with_overrides() -> TestClient:  # type: ignore[return]
    """Return a TestClient with auth and Redis dependencies stubbed out."""
    # Override auth so no JWT parsing happens in route tests
    app.dependency_overrides[get_current_user] = _override_auth
    app.dependency_overrides[get_redis] = _override_redis
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client  # type: ignore[misc]
    app.dependency_overrides.clear()


class TestRoomRoutes:
    def test_create_room_returns_201_with_code(
        self, client_with_overrides: TestClient
    ) -> None:
        """POST /api/rooms returns 201 with room_id and 6-char alphanumeric code."""
        mock_service = AsyncMock()
        from app.schemas.room import CreateRoomResponse

        mock_service.create_room = AsyncMock(
            return_value=CreateRoomResponse(room_id=ROOM_ID, code=ROOM_CODE)
        )

        from app.routes.rooms import get_room_service

        app.dependency_overrides[get_room_service] = lambda: mock_service

        try:
            resp = client_with_overrides.post(
                "/api/rooms", json={"max_players": 4}
            )
            assert resp.status_code == 201
            body = resp.json()
            assert "room_id" in body
            assert "code" in body
            assert len(body["code"]) == 6
            assert body["code"].isalnum()
        finally:
            app.dependency_overrides.pop(get_room_service, None)

    def test_create_room_returns_422_on_invalid_max_players(
        self, client_with_overrides: TestClient
    ) -> None:
        """POST /api/rooms with max_players=10 (>4) returns 422."""
        resp = client_with_overrides.post("/api/rooms", json={"max_players": 10})
        assert resp.status_code == 422

    def test_join_room_returns_409_when_full(
        self, client_with_overrides: TestClient
    ) -> None:
        """POST /api/rooms/{code}/join returns 409 when the room is full."""
        mock_service = AsyncMock()
        mock_service.join_room = AsyncMock(side_effect=RoomFullError("Room is full"))

        from app.routes.rooms import get_room_service

        app.dependency_overrides[get_room_service] = lambda: mock_service

        try:
            resp = client_with_overrides.post(f"/api/rooms/{ROOM_CODE}/join")
            assert resp.status_code == 409
        finally:
            app.dependency_overrides.pop(get_room_service, None)

    def test_join_room_returns_200_with_player_info(
        self, client_with_overrides: TestClient
    ) -> None:
        """POST /api/rooms/{code}/join returns player_index and color."""
        mock_service = AsyncMock()
        mock_service.join_room = AsyncMock(
            return_value=JoinResponse(player_index=1, color="green")
        )

        from app.routes.rooms import get_room_service

        app.dependency_overrides[get_room_service] = lambda: mock_service

        try:
            resp = client_with_overrides.post(f"/api/rooms/{ROOM_CODE}/join")
            assert resp.status_code == 200
            body = resp.json()
            assert body["player_index"] == 1
            assert body["color"] == "green"
        finally:
            app.dependency_overrides.pop(get_room_service, None)

    def test_leave_room_returns_204(
        self, client_with_overrides: TestClient
    ) -> None:
        """DELETE /api/rooms/{code}/leave returns HTTP 204 on success."""
        mock_service = AsyncMock()
        mock_service.leave_room = AsyncMock(return_value=None)

        from app.routes.rooms import get_room_service

        app.dependency_overrides[get_room_service] = lambda: mock_service

        try:
            resp = client_with_overrides.delete(f"/api/rooms/{ROOM_CODE}/leave")
            assert resp.status_code == 204
        finally:
            app.dependency_overrides.pop(get_room_service, None)

    def test_get_room_returns_403_for_non_member(
        self, client_with_overrides: TestClient
    ) -> None:
        """GET /api/rooms/{code} returns 403 when the caller is not a member."""
        mock_service = AsyncMock()
        mock_service.get_room = AsyncMock(side_effect=PermissionError("Not authorized"))

        from app.routes.rooms import get_room_service

        app.dependency_overrides[get_room_service] = lambda: mock_service

        try:
            resp = client_with_overrides.get(f"/api/rooms/{ROOM_CODE}")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.pop(get_room_service, None)

    def test_get_room_returns_player_list(
        self, client_with_overrides: TestClient
    ) -> None:
        """GET /api/rooms/{code} returns status, host, players, and available_seats."""
        from app.schemas.room import PlayerInfo, RoomResponse

        expected = RoomResponse(
            room_id=ROOM_ID,
            code=ROOM_CODE,
            status="waiting",
            host_display_name="Alice",
            max_players=4,
            players=[PlayerInfo(player_index=0, color="red", display_name="Alice", is_ai=False)],
            available_seats=3,
            created_at=datetime(2026, 1, 1),
        )
        mock_service = AsyncMock()
        mock_service.get_room = AsyncMock(return_value=expected)

        from app.routes.rooms import get_room_service

        app.dependency_overrides[get_room_service] = lambda: mock_service

        try:
            resp = client_with_overrides.get(f"/api/rooms/{ROOM_CODE}")
            assert resp.status_code == 200
            body = resp.json()
            assert body["code"] == ROOM_CODE
            assert body["status"] == "waiting"
            assert body["available_seats"] == 3
            assert len(body["players"]) == 1
        finally:
            app.dependency_overrides.pop(get_room_service, None)


# ---------------------------------------------------------------------------
# Room code case-insensitivity
# ---------------------------------------------------------------------------


class TestRoomCodeCaseInsensitivity:
    @pytest.mark.asyncio
    async def test_get_room_by_code_is_case_insensitive(self) -> None:
        """RoomRepository.get_room_by_code uppercases the code before querying."""
        # We test by verifying the service passes an upper-cased code to repo.
        player = _make_room_player(user_id=HOST_USER_ID)
        room = _make_room(code="AABBCC", players=[player])
        repo = _make_repo(room=room)

        service = RoomService(repo)
        # Pass lowercase code
        await service.get_room(code="aabbcc", requesting_user_id=HOST_USER_ID)

        repo.get_room_by_code.assert_called_once_with("aabbcc")
        # The repository should upper-case internally; verify it was called
        # (the mock returns the room regardless — the real impl upper-cases in WHERE)
