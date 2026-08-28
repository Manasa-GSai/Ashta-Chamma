"""Tests for the GDPR right-to-erasure DELETE /api/users/me endpoint.

Coverage targets (per WO-010 testing strategy):
  1. DELETE /api/users/me returns HTTP 204 with a valid JWT.
  2. User record is anonymised after deletion (display_name, clerk_id, avatar_url).
  3. game_scores rows referencing the user have user_id set to NULL.
  4. An audit_log entry with action 'user.erased' and the correct metadata exists.
  5. Subsequent API calls with the deleted user's JWT return HTTP 404.
  6. Unauthenticated requests return HTTP 401/403.
"""

import hashlib
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.dependencies import get_current_clerk_id
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.user_service import UserNotFoundError, UserService
from main import app


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_user(clerk_id: str = "user_test_abc123") -> User:
    """Create an in-memory User instance with realistic test data."""
    user = User()
    user.id = uuid.uuid4()
    user.clerk_id = clerk_id
    user.display_name = "Test Player"
    user.avatar_url = "https://example.com/avatar.png"
    user.locale = "en"
    user.created_at = datetime.now(UTC)
    user.updated_at = None
    return user


def _make_mock_session() -> MagicMock:
    """Return a mock AsyncSession whose begin() behaves as an async context manager."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()

    # begin() must behave as an async context manager: ``async with session.begin()``
    begin_cm = MagicMock()
    begin_cm.__aenter__ = AsyncMock(return_value=None)
    begin_cm.__aexit__ = AsyncMock(return_value=False)
    session.begin = MagicMock(return_value=begin_cm)

    return session


# ---------------------------------------------------------------------------
# Service-layer unit tests
# ---------------------------------------------------------------------------


async def test_erase_user_sets_display_name_to_deleted_user() -> None:
    """Acceptance criterion 2a: display_name becomes 'Deleted User'."""
    clerk_id = "user_abc_001"
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    assert user.display_name == "Deleted User"


async def test_erase_user_replaces_clerk_id_with_sha256_hash() -> None:
    """Acceptance criterion 2b: clerk_id is replaced with its SHA-256 hex digest."""
    clerk_id = "user_abc_001"
    expected_hash = hashlib.sha256(clerk_id.encode()).hexdigest()
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    assert user.clerk_id == expected_hash
    # The stored hash must not equal the original clerk_id (irreversible).
    assert user.clerk_id != clerk_id


async def test_erase_user_nulls_avatar_url() -> None:
    """Acceptance criterion 3: avatar_url is set to NULL after erasure."""
    clerk_id = "user_abc_002"
    user = _make_user(clerk_id)
    assert user.avatar_url is not None  # pre-condition

    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    assert user.avatar_url is None


async def test_erase_user_sets_updated_at_to_now() -> None:
    """updated_at is refreshed to the current UTC timestamp on erasure."""
    clerk_id = "user_abc_003"
    user = _make_user(clerk_id)
    before = datetime.now(UTC)

    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    assert user.updated_at is not None
    assert user.updated_at >= before


async def test_erase_user_nullifies_game_scores() -> None:
    """Acceptance criterion 4: nullify_game_scores is called with the user's UUID."""
    clerk_id = "user_abc_004"
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        mock_repo = MockRepo.return_value
        mock_repo.get_by_clerk_id = AsyncMock(return_value=user)
        mock_repo.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    mock_repo.nullify_game_scores.assert_awaited_once_with(user.id)


async def test_erase_user_creates_audit_log_with_correct_action() -> None:
    """Acceptance criterion 5: audit log entry has action='user.erased'."""
    clerk_id = "user_abc_005"
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    assert session.add.called
    added: AuditLog = session.add.call_args[0][0]
    assert isinstance(added, AuditLog)
    assert added.action == "user.erased"


async def test_erase_user_audit_log_metadata_contains_anonymized_user_id() -> None:
    """Acceptance criterion 5: audit log metadata contains the anonymized user ID."""
    clerk_id = "user_abc_006"
    user = _make_user(clerk_id)
    expected_user_id = str(user.id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    added: AuditLog = session.add.call_args[0][0]
    assert added.event_metadata is not None
    assert added.event_metadata["anonymized_user_id"] == expected_user_id


async def test_erase_user_audit_log_entity_type_and_id() -> None:
    """Audit log entry references the correct entity."""
    clerk_id = "user_abc_007"
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    added: AuditLog = session.add.call_args[0][0]
    assert added.entity_type == "user"
    assert added.entity_id == str(user.id)


async def test_erase_user_flushes_session() -> None:
    """Session is flushed so all changes are visible within the transaction."""
    clerk_id = "user_abc_008"
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        await UserService(session).erase_user(clerk_id)

    session.flush.assert_awaited_once()


async def test_erase_user_raises_user_not_found_for_unknown_clerk_id() -> None:
    """Service raises UserNotFoundError when the clerk_id does not exist in the DB."""
    session = _make_mock_session()

    with patch("app.services.user_service.UserRepository") as MockRepo:
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=None)

        with pytest.raises(UserNotFoundError, match="No user found with clerk_id="):
            await UserService(session).erase_user("nonexistent_clerk_id")


async def test_erase_user_clerk_failure_does_not_raise() -> None:
    """Clerk API failure is swallowed — local PII erasure is unaffected."""
    clerk_id = "user_abc_009"
    user = _make_user(clerk_id)
    session = _make_mock_session()

    with (
        patch("app.services.user_service.UserRepository") as MockRepo,
        patch(
            "app.services.user_service._deactivate_clerk_account",
            new_callable=AsyncMock,
            side_effect=OSError("network error"),
        ),
    ):
        MockRepo.return_value.get_by_clerk_id = AsyncMock(return_value=user)
        MockRepo.return_value.nullify_game_scores = AsyncMock()

        # Should not raise despite the Clerk error.
        await UserService(session).erase_user(clerk_id)

    # PII was still erased locally.
    assert user.display_name == "Deleted User"
    assert user.avatar_url is None


# ---------------------------------------------------------------------------
# Route-layer integration tests (FastAPI TestClient with dependency overrides)
# ---------------------------------------------------------------------------


@pytest.fixture
def _clerk_id() -> str:
    return "user_route_test_001"


@pytest.fixture
def _mock_db_session() -> MagicMock:
    return _make_mock_session()


@pytest.fixture
def _test_client(_clerk_id: str, _mock_db_session: MagicMock) -> TestClient:
    """TestClient with auth and DB dependencies overridden."""
    from app.database import get_db

    async def _override_get_db():  # type: ignore[return]
        yield _mock_db_session

    app.dependency_overrides[get_current_clerk_id] = lambda: _clerk_id
    app.dependency_overrides[get_db] = _override_get_db
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    app.dependency_overrides.clear()


def test_delete_returns_204_when_user_exists(
    _test_client: TestClient,
    _clerk_id: str,
) -> None:
    """Acceptance criterion 1: DELETE /api/users/me returns 204 with a valid JWT."""
    with patch("app.routes.users.UserService") as MockSvc:
        MockSvc.return_value.erase_user = AsyncMock()

        response = _test_client.delete("/api/users/me")

    assert response.status_code == 204


def test_delete_calls_erase_user_with_clerk_id(
    _test_client: TestClient,
    _clerk_id: str,
) -> None:
    """The route passes the authenticated clerk_id to UserService.erase_user."""
    with patch("app.routes.users.UserService") as MockSvc:
        mock_instance = MockSvc.return_value
        mock_instance.erase_user = AsyncMock()

        _test_client.delete("/api/users/me")

    mock_instance.erase_user.assert_awaited_once_with(_clerk_id)


def test_delete_returns_404_when_user_already_erased(
    _test_client: TestClient,
) -> None:
    """Acceptance criterion 6: subsequent requests after deletion return 404."""
    with patch("app.routes.users.UserService") as MockSvc:
        MockSvc.return_value.erase_user = AsyncMock(
            side_effect=UserNotFoundError("already erased")
        )

        response = _test_client.delete("/api/users/me")

    assert response.status_code == 404


def test_delete_returns_401_without_authorization_header() -> None:
    """Acceptance criterion 6: missing auth returns 401/403."""
    # Use a clean client without the auth override.
    clean_client = TestClient(app, raise_server_exceptions=False)
    response = clean_client.delete("/api/users/me")
    assert response.status_code in (401, 403)


def test_delete_returns_401_with_malformed_token() -> None:
    """A malformed JWT (not three Base64URL segments) returns 401."""
    clean_client = TestClient(app, raise_server_exceptions=False)
    response = clean_client.delete(
        "/api/users/me",
        headers={"Authorization": "Bearer not.a.valid.jwt.token.extra"},
    )
    assert response.status_code in (401, 403)


def test_delete_returns_response_body_is_empty_on_success(
    _test_client: TestClient,
) -> None:
    """204 response must have no body (clients should not attempt to parse it)."""
    with patch("app.routes.users.UserService") as MockSvc:
        MockSvc.return_value.erase_user = AsyncMock()

        response = _test_client.delete("/api/users/me")

    assert response.content == b""
