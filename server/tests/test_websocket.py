"""Tests for server/app/routes/websocket.py.

Covers:
 - WebSocket connection accepted for a room
 - ping → pong round-trip
 - Unknown message type returns NOT_IMPLEMENTED error
 - Latency is buffered after each message
 - flush_ws_metrics publishes buffered samples to CloudWatch
 - Eager flush when buffer reaches threshold
 - CloudWatch errors are swallowed
 - clear / get helpers for buffer inspection
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routes.websocket as ws_module
from app.routes.websocket import (
    router,
    flush_ws_metrics,
    get_ws_latency_buffer,
    clear_ws_latency_buffer,
    WS_NAMESPACE,
    _WS_BUFFER_FLUSH_THRESHOLD,
)


# ──────────────────────────────────────────────────────────────────────────────
# Fixture
# ──────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_ws_buffer():
    """Reset module-level WS latency buffer before each test."""
    clear_ws_latency_buffer()
    yield
    clear_ws_latency_buffer()


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    return app


# ──────────────────────────────────────────────────────────────────────────────
# WebSocket endpoint tests
# ──────────────────────────────────────────────────────────────────────────────


class TestWebSocketEndpoint:
    def test_connect_and_ping_pong(self) -> None:
        client = TestClient(_build_app())
        with client.websocket_connect("/ws/rooms/test-room-1") as ws:
            ws.send_json({"type": "ping"})
            data = ws.receive_json()
        assert data == {"type": "pong"}

    def test_unknown_type_returns_not_implemented(self) -> None:
        client = TestClient(_build_app())
        with client.websocket_connect("/ws/rooms/abc") as ws:
            ws.send_json({"type": "roll_request"})
            data = ws.receive_json()
        assert data["type"] == "error"
        assert data["code"] == "NOT_IMPLEMENTED"

    def test_latency_is_buffered_after_message(self) -> None:
        client = TestClient(_build_app())
        with client.websocket_connect("/ws/rooms/room-x") as ws:
            ws.send_json({"type": "ping"})
            ws.receive_json()

        buf = get_ws_latency_buffer()
        assert len(buf) == 1
        assert buf[0] > 0  # duration must be positive

    def test_multiple_messages_accumulate_in_buffer(self) -> None:
        client = TestClient(_build_app())
        with client.websocket_connect("/ws/rooms/multi") as ws:
            for _ in range(3):
                ws.send_json({"type": "ping"})
                ws.receive_json()

        assert len(get_ws_latency_buffer()) == 3


# ──────────────────────────────────────────────────────────────────────────────
# flush_ws_metrics tests
# ──────────────────────────────────────────────────────────────────────────────


class TestFlushWsMetrics:
    def test_no_op_when_empty(self) -> None:
        mock_cw = MagicMock()
        flush_ws_metrics(cloudwatch_client=mock_cw)
        mock_cw.put_metric_data.assert_not_called()

    def test_publishes_latency_samples(self) -> None:
        ws_module._ws_latency_buffer.extend([5.0, 10.0, 15.0])
        mock_cw = MagicMock()
        flush_ws_metrics(cloudwatch_client=mock_cw)

        mock_cw.put_metric_data.assert_called()

        all_metrics: list[dict] = []
        for c in mock_cw.put_metric_data.call_args_list:
            assert c.kwargs["Namespace"] == WS_NAMESPACE
            all_metrics.extend(c.kwargs["MetricData"])

        values = {m["Value"] for m in all_metrics}
        assert values == {5.0, 10.0, 15.0}

        for m in all_metrics:
            assert m["Unit"] == "Milliseconds"
            assert m["MetricName"] == "ws_message_latency_ms"

    def test_buffer_cleared_after_flush(self) -> None:
        ws_module._ws_latency_buffer.extend([1.0, 2.0])
        mock_cw = MagicMock()
        flush_ws_metrics(cloudwatch_client=mock_cw)
        assert get_ws_latency_buffer() == []

    def test_cloudwatch_error_is_swallowed(self) -> None:
        from botocore.exceptions import ClientError

        ws_module._ws_latency_buffer.append(99.0)
        mock_cw = MagicMock()
        mock_cw.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "PutMetricData",
        )
        # Should not raise
        flush_ws_metrics(cloudwatch_client=mock_cw)


# ──────────────────────────────────────────────────────────────────────────────
# Eager flush threshold test
# ──────────────────────────────────────────────────────────────────────────────


class TestEagerFlush:
    def test_eager_flush_at_threshold(self) -> None:
        """Buffer should be flushed (and cleared) when threshold is reached."""
        import app.routes.websocket as ws_mod
        from app.routes.websocket import _record_ws_latency

        mock_cw = MagicMock()
        with patch("boto3.client", return_value=mock_cw):
            # Fill buffer to just before threshold
            for _ in range(_WS_BUFFER_FLUSH_THRESHOLD - 1):
                ws_mod._ws_latency_buffer.append(1.0)

            # This call should trigger the eager flush
            _record_ws_latency(1.0)

        # After flush, buffer should be empty
        assert get_ws_latency_buffer() == []
        mock_cw.put_metric_data.assert_called()


# ──────────────────────────────────────────────────────────────────────────────
# Dispatch tests
# ──────────────────────────────────────────────────────────────────────────────


class TestDispatchMessage:
    def test_ping_returns_pong(self) -> None:
        from app.routes.websocket import _dispatch_message

        result = _dispatch_message("ping", {"type": "ping"}, "room-1")
        assert result == {"type": "pong"}

    def test_unknown_returns_error(self) -> None:
        from app.routes.websocket import _dispatch_message

        result = _dispatch_message("unknown_type", {"type": "unknown_type"}, "room-1")
        assert result["type"] == "error"
        assert result["code"] == "NOT_IMPLEMENTED"

    def test_empty_type_returns_error(self) -> None:
        from app.routes.websocket import _dispatch_message

        result = _dispatch_message("", {}, "room-1")
        assert result["type"] == "error"
