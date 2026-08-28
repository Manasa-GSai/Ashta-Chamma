"""Tests for GET and PUT /api/users/me endpoints.

Uses FastAPI dependency overrides so no real database or Clerk service is
needed.  The ``get_current_user`` dependency is replaced with a factory
that returns a pre-built :class:`~app.models.user.User` instance, and
``get_db`` is replaced with an async generator that yields a mock
:class:`~sqlalchemy.ext.asyncio.AsyncSession`.

Test matrix:
- GET /api/users/me returns HTTP 200 with correct profile JSON
- GET /api/users/me without JWT returns HTTP 401
- PUT /api/users/me updates display_name and locale, returns HTTP 200
- PUT /api/users/me rejects an invalid locale with HTTP 422
- PUT /api/users/me rejects a display_name over 100 chars with HTTP 422
- PUT /api/users/me rejects an empty display_name with HTTP 422
- PUT /api/users/me creates an AuditLog entry with the expected fields
"""

import uuid
from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.deps import get_current_user
from app.main import app
from app.models.audit_log import AuditLog
from app.models.user import User

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXED_USER_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
_FIXED_CREATED_AT = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_user(**overrides: Any) -> User:
    """Return a :class:`User` instance without a real DB session."""
    defaults: dict[str, Any] = {
        "id": _FIXED_USER_ID,
        "clerk_id": "user_clerk_abc123",
        "display_name": "Original Name",
        "avatar_url": None,
        "locale": "en",
        "created_at": _FIXED_CREATED_AT,
        "updated_at": _FIXED_CREATED_AT,
    }
    defaults.update(overrides)
    user = User.__new__(User)
    for key, value in defaults.items():
        setattr(user, key, value)
    return user


def _make_mock_db() -> AsyncMock:
    """Return a mock async session with the methods used by the routes."""
    db = AsyncMock(spec=["add", "flush", "refresh", "execute", "commit", "rollback"])
    db.add = MagicMock()  # synchronous in SQLAlchemy
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_db() -> AsyncMock:
    return _make_mock_db()


@pytest.fixture()
def authenticated_client(mock_db: AsyncMock) -> Generator[TestClient, None, None]:
    """TestClient whose ``get_current_user`` and ``get_db`` are overridden."""
    fake_user = _make_user()

    async def _override_get_db() -> AsyncGenerator[AsyncMock, None]:
        yield mock_db

    app.dependency_overrides[get_current_user] = lambda: fake_user
    app.dependency_overrides[get_db] = _override_get_db

    client = TestClient(app, raise_server_exceptions=True)
    yield client

    app.dependency_overrides.clear()


@pytest.fixture()
def unauthenticated_client() -> Generator[TestClient, None, None]:
    """TestClient with no dependency overrides (real auth path)."""
    # Clear any leftover overrides from other tests.
    app.dependency_overrides.clear()
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/users/me
# ---------------------------------------------------------------------------


def test_get_me_returns_200_with_profile(authenticated_client: TestClient) -> None:
    response = authenticated_client.get("/api/users/me")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(_FIXED_USER_ID)
    assert data["clerk_id"] == "user_clerk_abc123"
    assert data["display_name"] == "Original Name"
    assert data["avatar_url"] is None
    assert data["locale"] == "en"
    assert "created_at" in data


def test_get_me_excludes_internal_fields(authenticated_client: TestClient) -> None:
    """Response must not expose updated_at or any hashed/internal columns."""
    response = authenticated_client.get("/api/users/me")

    assert response.status_code == 200
    data = response.json()
    # These fields exist on the ORM model but must not appear in the API response.
    assert "updated_at" not in data
    assert "hashed_password" not in data


def test_get_me_without_jwt_returns_401(unauthenticated_client: TestClient) -> None:
    response = unauthenticated_client.get("/api/users/me")

    assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /api/users/me — happy path
# ---------------------------------------------------------------------------


def test_put_me_updates_display_name_and_locale(
    authenticated_client: TestClient, mock_db: AsyncMock
) -> None:
    payload = {"display_name": "New Name", "locale": "te"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "New Name"
    assert data["locale"] == "te"


def test_put_me_returns_updated_profile(
    authenticated_client: TestClient,
) -> None:
    payload = {"display_name": "Updated Display", "locale": "en"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(_FIXED_USER_ID)
    assert data["display_name"] == "Updated Display"


def test_put_me_calls_db_flush_and_add(
    authenticated_client: TestClient, mock_db: AsyncMock
) -> None:
    """Route must flush the session so changes are visible within the transaction."""
    payload = {"display_name": "Flushed Name", "locale": "en"}
    authenticated_client.put("/api/users/me", json=payload)

    mock_db.flush.assert_awaited_once()
    mock_db.add.assert_called()


# ---------------------------------------------------------------------------
# PUT /api/users/me — audit log
# ---------------------------------------------------------------------------


def test_put_me_creates_audit_log_entry(
    authenticated_client: TestClient, mock_db: AsyncMock
) -> None:
    """An AuditLog row with action 'user.profile_updated' must be added."""
    payload = {"display_name": "Audited Name", "locale": "te"}
    authenticated_client.put("/api/users/me", json=payload)

    # Collect every object passed to db.add()
    added_objects = [c.args[0] for c in mock_db.add.call_args_list]
    audit_entries = [obj for obj in added_objects if isinstance(obj, AuditLog)]

    assert len(audit_entries) == 1, "Exactly one AuditLog entry must be created"
    entry = audit_entries[0]
    assert entry.action == "user.profile_updated"
    assert entry.actor_id == _FIXED_USER_ID


def test_put_me_audit_log_contains_changed_fields(
    authenticated_client: TestClient, mock_db: AsyncMock
) -> None:
    """AuditLog metadata must record the before/after values for each changed field."""
    payload = {"display_name": "Changed Name", "locale": "te"}
    authenticated_client.put("/api/users/me", json=payload)

    added_objects = [c.args[0] for c in mock_db.add.call_args_list]
    entry = next(obj for obj in added_objects if isinstance(obj, AuditLog))

    assert entry.metadata is not None
    changed = entry.metadata["changed_fields"]
    # Both fields differ from the fixture defaults ("Original Name" / "en")
    assert "display_name" in changed
    assert changed["display_name"]["from"] == "Original Name"
    assert changed["display_name"]["to"] == "Changed Name"
    assert "locale" in changed
    assert changed["locale"]["from"] == "en"
    assert changed["locale"]["to"] == "te"


# ---------------------------------------------------------------------------
# PUT /api/users/me — validation errors
# ---------------------------------------------------------------------------


def test_put_me_rejects_invalid_locale(authenticated_client: TestClient) -> None:
    """A locale value other than 'en' or 'te' must return HTTP 422."""
    payload = {"display_name": "Valid Name", "locale": "fr"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 422


def test_put_me_rejects_display_name_over_100_chars(
    authenticated_client: TestClient,
) -> None:
    payload = {"display_name": "x" * 101, "locale": "en"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 422


def test_put_me_rejects_empty_display_name(authenticated_client: TestClient) -> None:
    payload = {"display_name": "", "locale": "en"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 422


def test_put_me_rejects_html_only_display_name(
    authenticated_client: TestClient,
) -> None:
    """A name consisting entirely of HTML tags must fail after stripping."""
    payload = {"display_name": "<script>alert(1)</script>", "locale": "en"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 422


def test_put_me_strips_html_from_display_name(
    authenticated_client: TestClient,
) -> None:
    """HTML tags embedded in an otherwise valid name must be stripped."""
    payload = {"display_name": "Alice<b>Bold</b>", "locale": "en"}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 200
    assert response.json()["display_name"] == "AliceBold"


def test_put_me_rejects_missing_fields(authenticated_client: TestClient) -> None:
    """Both display_name and locale are required."""
    response = authenticated_client.put("/api/users/me", json={"display_name": "Name"})

    assert response.status_code == 422


def test_put_me_rejects_integer_locale(authenticated_client: TestClient) -> None:
    """Strict mode must reject an integer where a string is expected."""
    # strict=True in UserUpdateRequest means no implicit coercion
    payload = {"display_name": "Valid Name", "locale": 1}
    response = authenticated_client.put("/api/users/me", json=payload)

    assert response.status_code == 422
