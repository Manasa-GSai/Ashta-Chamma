"""Tests for the CloudWatch metrics middleware.

Covers:
 - Happy path: duration is buffered on normal requests
 - 5xx responses increment error counter
 - flush_metrics publishes correct metric names and units
 - Empty buffer: flush is a no-op (no CloudWatch call)
 - CloudWatch errors are swallowed (never propagated)
 - Module-level buffers are reset after flush
"""

from unittest.mock import MagicMock, patch, call
import pytest

import app.middleware.metrics as metrics_module
from app.middleware.metrics import (
    MetricsMiddleware,
    flush_metrics,
    API_NAMESPACE,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────


def _reset_buffers() -> None:
    """Reset module-level buffers between tests."""
    metrics_module._pending_durations.clear()
    metrics_module._request_count = 0
    metrics_module._error_5xx_count = 0


# ──────────────────────────────────────────────────────────────────────────────
# flush_metrics tests
# ──────────────────────────────────────────────────────────────────────────────


class TestFlushMetrics:
    def setup_method(self) -> None:
        _reset_buffers()

    def test_no_op_when_buffers_empty(self) -> None:
        mock_cw = MagicMock()
        flush_metrics(cloudwatch_client=mock_cw)
        mock_cw.put_metric_data.assert_not_called()

    def test_publishes_latency_samples(self) -> None:
        metrics_module._pending_durations.extend([10.0, 20.0, 30.0])
        metrics_module._request_count = 3

        mock_cw = MagicMock()
        flush_metrics(cloudwatch_client=mock_cw)

        # Verify at least one put_metric_data call was made
        mock_cw.put_metric_data.assert_called()

        # Collect all MetricData items published across all calls
        all_metrics = []
        for call_args in mock_cw.put_metric_data.call_args_list:
            kwargs = call_args.kwargs
            assert kwargs["Namespace"] == API_NAMESPACE
            all_metrics.extend(kwargs["MetricData"])

        latency_names = [m["MetricName"] for m in all_metrics if m["MetricName"] == "api_response_time_ms"]
        assert len(latency_names) == 3

        values = [m["Value"] for m in all_metrics if m["MetricName"] == "api_response_time_ms"]
        assert set(values) == {10.0, 20.0, 30.0}

    def test_publishes_request_count(self) -> None:
        metrics_module._request_count = 7
        mock_cw = MagicMock()
        flush_metrics(cloudwatch_client=mock_cw)

        all_metrics: list[dict] = []
        for c in mock_cw.put_metric_data.call_args_list:
            all_metrics.extend(c.kwargs["MetricData"])

        request_metrics = [m for m in all_metrics if m["MetricName"] == "http_request_count"]
        assert len(request_metrics) == 1
        assert request_metrics[0]["Value"] == 7.0
        assert request_metrics[0]["Unit"] == "Count"

    def test_publishes_error_count(self) -> None:
        metrics_module._request_count = 10
        metrics_module._error_5xx_count = 2
        mock_cw = MagicMock()
        flush_metrics(cloudwatch_client=mock_cw)

        all_metrics: list[dict] = []
        for c in mock_cw.put_metric_data.call_args_list:
            all_metrics.extend(c.kwargs["MetricData"])

        error_metrics = [m for m in all_metrics if m["MetricName"] == "http_5xx_count"]
        assert len(error_metrics) == 1
        assert error_metrics[0]["Value"] == 2.0

    def test_buffers_are_reset_after_flush(self) -> None:
        metrics_module._pending_durations.extend([5.0])
        metrics_module._request_count = 1
        metrics_module._error_5xx_count = 0
        mock_cw = MagicMock()
        flush_metrics(cloudwatch_client=mock_cw)

        assert metrics_module._pending_durations == []
        assert metrics_module._request_count == 0
        assert metrics_module._error_5xx_count == 0

    def test_cloudwatch_error_is_swallowed(self) -> None:
        """CloudWatch failures must never propagate to callers."""
        from botocore.exceptions import ClientError

        metrics_module._request_count = 1
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "ServiceUnavailable", "Message": "Throttled"}},
            "PutMetricData",
        )

        # Should not raise
        flush_metrics(cloudwatch_client=mock_cw)

    def test_zero_error_count_not_published(self) -> None:
        """http_5xx_count should only be sent when errors actually occurred."""
        metrics_module._request_count = 5
        metrics_module._error_5xx_count = 0
        mock_cw = MagicMock()
        flush_metrics(cloudwatch_client=mock_cw)

        all_metrics: list[dict] = []
        for c in mock_cw.put_metric_data.call_args_list:
            all_metrics.extend(c.kwargs["MetricData"])

        error_metrics = [m for m in all_metrics if m["MetricName"] == "http_5xx_count"]
        assert error_metrics == []


# ──────────────────────────────────────────────────────────────────────────────
# MetricsMiddleware tests (via FastAPI test client)
# ──────────────────────────────────────────────────────────────────────────────


class TestMetricsMiddleware:
    def setup_method(self) -> None:
        _reset_buffers()

    def test_duration_buffered_on_success(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.add_middleware(MetricsMiddleware)

        @test_app.get("/ping")
        async def ping() -> dict:
            return {"ok": True}

        client = TestClient(test_app)
        client.get("/ping")

        assert len(metrics_module._pending_durations) == 1
        assert metrics_module._pending_durations[0] > 0
        assert metrics_module._request_count == 1
        assert metrics_module._error_5xx_count == 0

    def test_5xx_increments_error_counter(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.add_middleware(MetricsMiddleware)

        @test_app.get("/boom")
        async def boom() -> dict:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=500, content={"error": "server error"})

        client = TestClient(test_app, raise_server_exceptions=False)
        client.get("/boom")

        assert metrics_module._error_5xx_count == 1
        assert metrics_module._request_count == 1

    def test_4xx_does_not_increment_error_counter(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.add_middleware(MetricsMiddleware)

        @test_app.get("/notfound")
        async def notfound() -> dict:
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=404, content={"detail": "not found"})

        client = TestClient(test_app)
        client.get("/notfound")

        assert metrics_module._error_5xx_count == 0
        assert metrics_module._request_count == 1

    def test_multiple_requests_accumulate(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        test_app = FastAPI()
        test_app.add_middleware(MetricsMiddleware)

        @test_app.get("/x")
        async def x() -> dict:
            return {}

        client = TestClient(test_app)
        for _ in range(5):
            client.get("/x")

        assert metrics_module._request_count == 5
        assert len(metrics_module._pending_durations) == 5
