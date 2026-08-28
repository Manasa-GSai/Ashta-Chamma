"""Tests for server/app/main.py.

Covers:
 - Health check endpoint returns 200 with expected body
 - App exposes expected metadata (title, version)
 - Metrics middleware is registered
 - WebSocket router is mounted
 - Background task starts on app startup
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthCheck:
    def test_returns_200(self) -> None:
        from app.main import app

        client = TestClient(app)
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_body_has_status_ok(self) -> None:
        from app.main import app

        client = TestClient(app)
        data = client.get("/api/health").json()
        assert data["status"] == "ok"

    def test_body_has_version(self) -> None:
        from app.main import app

        client = TestClient(app)
        data = client.get("/api/health").json()
        assert "version" in data
        assert isinstance(data["version"], str)


class TestAppMetadata:
    def test_title(self) -> None:
        from app.main import app

        assert "Ashta Chamma" in app.title

    def test_version(self) -> None:
        from app.main import app

        assert app.version == "0.1.0"


class TestMiddlewareRegistration:
    def test_metrics_middleware_present(self) -> None:
        from app.main import app
        from app.middleware.metrics import MetricsMiddleware

        middleware_types = [m.cls for m in app.user_middleware]
        assert MetricsMiddleware in middleware_types


class TestWebSocketRouterMounted:
    def test_ws_route_exists(self) -> None:
        from app.main import app

        # Collect all route paths; WebSocket routes use different Route types
        paths = []
        for route in app.routes:
            if hasattr(route, "path"):
                paths.append(route.path)

        assert any("/ws/rooms/{room_id}" in p for p in paths), (
            f"WebSocket route not found. Routes: {paths}"
        )


class TestPublishGameMetrics:
    def test_publish_calls_boto3(self) -> None:
        """_publish_game_metrics should call boto3 put_metric_data."""
        from app.main import _publish_game_metrics

        mock_client = MagicMock()
        with patch("boto3.client", return_value=mock_client):
            _publish_game_metrics(active_rooms=3, connected_players=12)

        mock_client.put_metric_data.assert_called_once()
        call_kwargs = mock_client.put_metric_data.call_args.kwargs
        assert call_kwargs["Namespace"] == "AshtaChamma/Game"

        names = {m["MetricName"] for m in call_kwargs["MetricData"]}
        assert "active_rooms_count" in names
        assert "connected_players_count" in names

    def test_boto3_error_is_swallowed(self) -> None:
        """CloudWatch failures in game metrics must not crash the app."""
        from app.main import _publish_game_metrics

        with patch("boto3.client", side_effect=Exception("network error")):
            # Should not raise
            _publish_game_metrics()


class TestMetricsBackgroundTask:
    @pytest.mark.asyncio
    async def test_task_calls_flush_and_game_metrics(self) -> None:
        from app.main import _metrics_background_task

        with (
            patch("app.main.flush_metrics") as mock_flush,
            patch("app.main._publish_game_metrics") as mock_game,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            # Run one iteration then cancel
            mock_sleep.side_effect = [None, asyncio.CancelledError()]
            with pytest.raises(asyncio.CancelledError):
                await _metrics_background_task()

        mock_flush.assert_called_once()
        mock_game.assert_called_once()
