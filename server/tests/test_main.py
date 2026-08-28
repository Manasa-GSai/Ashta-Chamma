"""Tests for FastAPI application setup and lifespan hooks.

Verifies:
- The ``app`` object is a FastAPI instance
- The ``/api/health`` route is registered
- Lifespan startup initialises the redis_manager singleton
- Lifespan shutdown closes the manager and clears the singleton
- REDIS_URL environment variable is forwarded to RedisManager
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

import app.redis as redis_module
from app.main import app, lifespan


class TestAppInstance:
    def test_app_is_fastapi_instance(self) -> None:
        assert isinstance(app, FastAPI)

    def test_api_health_route_registered(self) -> None:
        routes = [r.path for r in app.routes]  # type: ignore[attr-defined]
        assert "/api/health" in routes


class TestLifespan:
    async def test_startup_initialises_redis_manager(self) -> None:
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.is_connected = True
        mock_manager.close = AsyncMock()

        with patch("app.main.RedisManager", return_value=mock_manager):
            async with lifespan(app):
                assert redis_module.redis_manager is mock_manager
                mock_manager.initialize.assert_awaited_once()

    async def test_shutdown_closes_manager_and_clears_singleton(self) -> None:
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.is_connected = False
        mock_manager.close = AsyncMock()

        with patch("app.main.RedisManager", return_value=mock_manager):
            async with lifespan(app):
                pass  # yield point

        mock_manager.close.assert_awaited_once()
        assert redis_module.redis_manager is None

    async def test_lifespan_uses_redis_url_env_var(self) -> None:
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.is_connected = True
        mock_manager.close = AsyncMock()

        custom_url = "rediss://custom.cache.example.com:6380"
        with (
            patch.dict(os.environ, {"REDIS_URL": custom_url}),
            patch("app.main.RedisManager", return_value=mock_manager) as mock_cls,
        ):
            async with lifespan(app):
                pass

        mock_cls.assert_called_once_with(custom_url)

    async def test_lifespan_defaults_to_local_redis_when_env_missing(self) -> None:
        mock_manager = MagicMock()
        mock_manager.initialize = AsyncMock()
        mock_manager.is_connected = False
        mock_manager.close = AsyncMock()

        env_without_redis = {k: v for k, v in os.environ.items() if k != "REDIS_URL"}
        with (
            patch.dict(os.environ, env_without_redis, clear=True),
            patch("app.main.RedisManager", return_value=mock_manager) as mock_cls,
        ):
            async with lifespan(app):
                pass

        called_url: str = mock_cls.call_args.args[0]
        assert called_url.startswith("redis://")
