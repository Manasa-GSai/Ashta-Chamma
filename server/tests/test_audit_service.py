"""Tests for audit_service, AuditLog model, and admin audit-logs endpoint.

Coverage checklist:
  - log_action() produces an AuditLog with all required fields
  - log_action() accepts None actor_id for system events
  - log_action() accepts None metadata
  - created_at is a timezone-aware UTC datetime
  - CRITICAL_ACTIONS contains every event required by acceptance criteria
  - ORM before_update listener raises RuntimeError (immutability enforcement)
  - ORM before_delete listener raises RuntimeError (immutability enforcement)
  - Admin endpoint returns 404 when feature flag is off
  - Admin endpoint returns 401 with wrong secret
  - Admin endpoint passes with correct secret
  - Admin endpoint returns filtered query results
  - Admin endpoint returns 503 when ADMIN_SECRET is not configured
"""

import os
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.audit_log import AuditLog, _prevent_delete, _prevent_update
from app.services.audit_service import CRITICAL_ACTIONS, log_action


# ---------------------------------------------------------------------------
# log_action() happy-path tests
# ---------------------------------------------------------------------------


class TestLogAction:
    """Tests for audit_service.log_action()."""

    async def test_log_action_creates_entry_with_all_fields(self) -> None:
        """log_action() must create an AuditLog with every provided field."""
        session = AsyncMock()
        extra: dict[str, Any] = {"room_code": "ABC123", "player_count": 4}

        entry = await log_action(
            session,
            actor_id="user_clerk_abc123",
            action="room.created",
            entity_type="room",
            entity_id="550e8400-e29b-41d4-a716-446655440000",
            metadata=extra,
        )

        assert isinstance(entry, AuditLog)
        assert entry.actor_id == "user_clerk_abc123"
        assert entry.action == "room.created"
        assert entry.entity_type == "room"
        assert entry.entity_id == "550e8400-e29b-41d4-a716-446655440000"
        assert entry.log_metadata == extra
        assert isinstance(entry.created_at, datetime)

    async def test_log_action_calls_session_add_and_flush(self) -> None:
        """log_action() must add the entry to the session and flush."""
        session = AsyncMock()

        entry = await log_action(
            session,
            actor_id="user_123",
            action="auth.login",
        )

        session.add.assert_called_once_with(entry)
        session.flush.assert_awaited_once()

    async def test_log_action_allows_null_actor_for_system_events(self) -> None:
        """System events (e.g. room.auto_closed) may have actor_id=None."""
        session = AsyncMock()

        entry = await log_action(
            session,
            actor_id=None,
            action="room.auto_closed",
            entity_type="room",
            entity_id="some-room-id",
        )

        assert entry.actor_id is None
        assert entry.action == "room.auto_closed"

    async def test_log_action_allows_null_metadata(self) -> None:
        """metadata is optional and defaults to None."""
        session = AsyncMock()

        entry = await log_action(
            session,
            actor_id="user_123",
            action="auth.logout",
        )

        assert entry.log_metadata is None

    async def test_log_action_created_at_is_timezone_aware(self) -> None:
        """created_at must be a timezone-aware UTC datetime."""
        session = AsyncMock()

        entry = await log_action(
            session,
            actor_id="user_123",
            action="auth.login",
        )

        assert entry.created_at.tzinfo is not None

    async def test_log_action_optional_fields_default_to_none(self) -> None:
        """entity_type and entity_id default to None when not supplied."""
        session = AsyncMock()

        entry = await log_action(
            session,
            actor_id="user_abc",
            action="auth.failed",
        )

        assert entry.entity_type is None
        assert entry.entity_id is None


# ---------------------------------------------------------------------------
# CRITICAL_ACTIONS coverage check
# ---------------------------------------------------------------------------


class TestCriticalActions:
    """Verify CRITICAL_ACTIONS covers all acceptance-criteria events."""

    def test_critical_actions_contains_all_required_events(self) -> None:
        """CRITICAL_ACTIONS must include every event from the acceptance criteria."""
        required = {
            "auth.login",
            "auth.failed",
            "auth.logout",
            "user.profile_updated",
            "user.erased",
            "room.created",
            "room.joined",
            "room.left",
            "room.auto_closed",
            "game.started",
            "game.roll",
            "game.move",
            "game.capture",
            "game.completed",
        }
        missing = required - CRITICAL_ACTIONS
        assert not missing, f"Missing critical actions: {missing}"

    def test_critical_actions_is_frozenset(self) -> None:
        """CRITICAL_ACTIONS must be immutable."""
        assert isinstance(CRITICAL_ACTIONS, frozenset)


# ---------------------------------------------------------------------------
# AuditLog immutability (ORM event listener) tests
# ---------------------------------------------------------------------------


class TestAuditLogImmutability:
    """Verify append-only enforcement raises on UPDATE and DELETE."""

    def test_before_update_listener_raises_runtime_error(self) -> None:
        """ORM before_update listener must raise RuntimeError."""
        entry = AuditLog()
        with pytest.raises(RuntimeError, match="immutable"):
            _prevent_update(
                mapper=MagicMock(), connection=MagicMock(), target=entry
            )

    def test_before_delete_listener_raises_runtime_error(self) -> None:
        """ORM before_delete listener must raise RuntimeError."""
        entry = AuditLog()
        with pytest.raises(RuntimeError, match="immutable"):
            _prevent_delete(
                mapper=MagicMock(), connection=MagicMock(), target=entry
            )

    def test_update_error_message_mentions_soc2(self) -> None:
        """UPDATE error must mention SOC 2 policy for operator clarity."""
        entry = AuditLog()
        with pytest.raises(RuntimeError, match="SOC 2"):
            _prevent_update(
                mapper=MagicMock(), connection=MagicMock(), target=entry
            )

    def test_delete_error_message_mentions_retention_period(self) -> None:
        """DELETE error must mention the 1-year retention policy."""
        entry = AuditLog()
        with pytest.raises(RuntimeError, match="1 year"):
            _prevent_delete(
                mapper=MagicMock(), connection=MagicMock(), target=entry
            )


# ---------------------------------------------------------------------------
# Admin endpoint tests
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    """Tests for the _require_admin dependency gate."""

    def test_returns_404_when_feature_flag_is_false(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Endpoint must return 404 (not reveal its existence) when disabled."""
        from fastapi import HTTPException
        from app.routes.admin import _require_admin

        monkeypatch.setenv("ADMIN_AUDIT_LOGS_ENABLED", "false")
        with pytest.raises(HTTPException) as exc_info:
            _require_admin(credentials=None)
        assert exc_info.value.status_code == 404

    def test_returns_404_when_flag_is_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Endpoint defaults to disabled when env var is not set."""
        from fastapi import HTTPException
        from app.routes.admin import _require_admin

        monkeypatch.delenv("ADMIN_AUDIT_LOGS_ENABLED", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            _require_admin(credentials=None)
        assert exc_info.value.status_code == 404

    def test_returns_503_when_secret_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Endpoint must fail closed (503) when ADMIN_SECRET is missing."""
        from fastapi import HTTPException
        from app.routes.admin import _require_admin

        monkeypatch.setenv("ADMIN_AUDIT_LOGS_ENABLED", "true")
        monkeypatch.delenv("ADMIN_SECRET", raising=False)
        with pytest.raises(HTTPException) as exc_info:
            _require_admin(credentials=None)
        assert exc_info.value.status_code == 503

    def test_returns_401_with_wrong_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Endpoint must return 401 when the bearer token is wrong."""
        from fastapi import HTTPException
        from fastapi.security import HTTPAuthorizationCredentials
        from app.routes.admin import _require_admin

        monkeypatch.setenv("ADMIN_AUDIT_LOGS_ENABLED", "true")
        monkeypatch.setenv("ADMIN_SECRET", "correct-secret")
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="wrong-secret"
        )
        with pytest.raises(HTTPException) as exc_info:
            _require_admin(credentials=creds)
        assert exc_info.value.status_code == 401

    def test_passes_with_correct_secret(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Endpoint must succeed (return None) when all checks pass."""
        from app.routes.admin import _require_admin
        from fastapi.security import HTTPAuthorizationCredentials

        monkeypatch.setenv("ADMIN_AUDIT_LOGS_ENABLED", "true")
        monkeypatch.setenv("ADMIN_SECRET", "my-super-secret")
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="my-super-secret"
        )
        result = _require_admin(credentials=creds)
        assert result is None


class TestGetAuditLogs:
    """Tests for the GET /api/admin/audit-logs route handler."""

    async def test_returns_matching_entries(self) -> None:
        """Handler must return items from the database with correct fields."""
        from app.routes.admin import get_audit_logs, AuditLogListResponse

        now = datetime.now(tz=timezone.utc)
        mock_row = AuditLog(
            id=1,
            actor_id="user_123",
            action="auth.login",
            entity_type="user",
            entity_id="user_123",
            log_metadata={"ip": "127.0.0.1"},
            created_at=now,
        )

        session = AsyncMock()
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = [mock_row]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        session.execute = AsyncMock(side_effect=[data_result, count_result])

        response = await get_audit_logs(
            action="auth.login",
            entity_type=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
            _=None,
            session=session,
        )

        assert isinstance(response, AuditLogListResponse)
        assert response.total == 1
        assert response.limit == 50
        assert response.offset == 0
        assert len(response.items) == 1
        item = response.items[0]
        assert item.action == "auth.login"
        assert item.actor_id == "user_123"
        assert item.metadata == {"ip": "127.0.0.1"}

    async def test_returns_empty_list_when_no_matches(self) -> None:
        """Handler must return an empty list when no rows match."""
        from app.routes.admin import get_audit_logs, AuditLogListResponse

        session = AsyncMock()
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        session.execute = AsyncMock(side_effect=[data_result, count_result])

        response = await get_audit_logs(
            action="game.capture",
            entity_type=None,
            date_from=None,
            date_to=None,
            limit=50,
            offset=0,
            _=None,
            session=session,
        )

        assert isinstance(response, AuditLogListResponse)
        assert response.total == 0
        assert response.items == []

    async def test_calls_execute_twice_for_data_and_count(self) -> None:
        """Handler must execute two queries: one for data, one for count."""
        from app.routes.admin import get_audit_logs

        session = AsyncMock()
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        session.execute = AsyncMock(side_effect=[data_result, count_result])

        await get_audit_logs(
            action=None,
            entity_type=None,
            date_from=None,
            date_to=None,
            limit=10,
            offset=0,
            _=None,
            session=session,
        )

        assert session.execute.await_count == 2

    async def test_respects_pagination_parameters(self) -> None:
        """Handler must pass limit/offset through to the response."""
        from app.routes.admin import get_audit_logs, AuditLogListResponse

        session = AsyncMock()
        data_result = MagicMock()
        data_result.scalars.return_value.all.return_value = []
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        session.execute = AsyncMock(side_effect=[data_result, count_result])

        response = await get_audit_logs(
            action=None,
            entity_type=None,
            date_from=None,
            date_to=None,
            limit=25,
            offset=100,
            _=None,
            session=session,
        )

        assert isinstance(response, AuditLogListResponse)
        assert response.limit == 25
        assert response.offset == 100
