"""Unit tests for the FastAPI application entry point.

Covers:
- Health endpoint happy path
- 500 error responses do not leak Sentry event IDs or internal details
- Sentry is initialised with the correct parameters when DSN is present
- Sentry is NOT initialised when DSN is absent
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


def test_health_endpoint_returns_200() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_endpoint_body_contains_ok_status() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.json()["status"] == "ok"


def test_health_endpoint_body_contains_version() -> None:
    client = TestClient(app)
    response = client.get("/api/health")
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)


# ---------------------------------------------------------------------------
# Unhandled exception handling — must not leak internals to client
# ---------------------------------------------------------------------------

# Shared router for routes that intentionally raise errors in tests.
_error_router = APIRouter()


@_error_router.get("/test-unhandled-error")
async def _boom_route() -> None:
    raise RuntimeError("secret internal message — must not reach client")


app.include_router(_error_router)
_error_client = TestClient(app, raise_server_exceptions=False)


def test_unhandled_exception_returns_500() -> None:
    response = _error_client.get("/test-unhandled-error")
    assert response.status_code == 500


def test_unhandled_exception_response_body_is_generic() -> None:
    response = _error_client.get("/test-unhandled-error")
    assert response.json() == {"detail": "Internal server error"}


def test_unhandled_exception_does_not_leak_error_message() -> None:
    response = _error_client.get("/test-unhandled-error")
    body_text = response.text
    assert "secret internal message" not in body_text


def test_unhandled_exception_does_not_leak_sentry_event_id() -> None:
    response = _error_client.get("/test-unhandled-error")
    body_text = response.text.lower()
    # The response must not contain any reference to Sentry or its event IDs.
    assert "sentry" not in body_text


# ---------------------------------------------------------------------------
# Sentry initialisation — DSN controls whether SDK is activated
# ---------------------------------------------------------------------------


def test_sentry_init_called_when_dsn_is_set() -> None:
    """Re-importing main with a DSN set should call sentry_sdk.init."""
    import importlib

    import sentry_sdk

    with patch.dict(os.environ, {"SENTRY_DSN": "https://abc@sentry.io/1"}):
        with patch.object(sentry_sdk, "init") as mock_init:
            import app.config as cfg_module
            import app.main as main_module

            importlib.reload(cfg_module)
            importlib.reload(main_module)
            mock_init.assert_called_once()


def test_sentry_init_not_called_when_dsn_is_empty() -> None:
    """Re-importing main without a DSN must not call sentry_sdk.init."""
    import importlib

    import sentry_sdk

    with patch.dict(os.environ, {}, clear=True):
        with patch.object(sentry_sdk, "init") as mock_init:
            import app.config as cfg_module
            import app.main as main_module

            importlib.reload(cfg_module)
            importlib.reload(main_module)
            mock_init.assert_not_called()


def test_sentry_init_disables_default_pii() -> None:
    """Sentry must never send PII (email, names) — only user IDs are permitted."""
    import importlib

    import sentry_sdk

    with patch.dict(os.environ, {"SENTRY_DSN": "https://abc@sentry.io/1"}):
        with patch.object(sentry_sdk, "init") as mock_init:
            import app.config as cfg_module
            import app.main as main_module

            importlib.reload(cfg_module)
            importlib.reload(main_module)

            _args, kwargs = mock_init.call_args
            assert kwargs.get("send_default_pii") is False


def test_sentry_captures_exception_in_handler() -> None:
    """The exception handler must forward the exception to Sentry."""
    import sentry_sdk

    with patch.object(sentry_sdk, "capture_exception") as mock_capture:
        _error_client.get("/test-unhandled-error")
        mock_capture.assert_called_once()
