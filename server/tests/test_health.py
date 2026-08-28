"""Tests for the /api/health endpoint.

Verifies:
- 200 response with correct schema
- Redis status is ``"connected"`` when ping succeeds
- Redis status is ``"unavailable"`` when ping fails
- Redis status is ``"unavailable"`` when redis_manager is None (e.g. startup
  not complete)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.redis as redis_module
from app.routes.health import health_check


class TestHealthCheck:
    async def test_returns_ok_status_and_version(self) -> None:
        from app import __version__

        mock_manager = MagicMock()
        mock_manager.ping = AsyncMock(return_value=True)

        with patch.object(redis_module, "redis_manager", mock_manager):
            response = await health_check()

        assert response.status == "ok"
        assert response.version == __version__

    async def test_redis_connected_when_ping_succeeds(self) -> None:
        mock_manager = MagicMock()
        mock_manager.ping = AsyncMock(return_value=True)

        with patch.object(redis_module, "redis_manager", mock_manager):
            response = await health_check()

        assert response.redis == "connected"

    async def test_redis_unavailable_when_ping_fails(self) -> None:
        mock_manager = MagicMock()
        mock_manager.ping = AsyncMock(return_value=False)

        with patch.object(redis_module, "redis_manager", mock_manager):
            response = await health_check()

        assert response.redis == "unavailable"

    async def test_redis_unavailable_when_manager_is_none(self) -> None:
        with patch.object(redis_module, "redis_manager", None):
            response = await health_check()

        assert response.redis == "unavailable"
        assert response.status == "ok"
