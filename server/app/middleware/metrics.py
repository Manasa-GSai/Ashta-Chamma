"""CloudWatch metrics middleware for HTTP request instrumentation.

Records request duration and HTTP status codes and buffers them for
periodic bulk publishing to CloudWatch via ``flush_metrics()``.

Namespace: AshtaChamma/API

Design notes:
- Metrics are buffered in module-level lists to avoid a per-request
  CloudWatch API call (which would add latency and cost).
- ``flush_metrics()`` is called every 60 seconds by the background task
  in ``main.py`` — standard resolution to stay within the $100/month budget.
- A threading.Lock guards the shared buffers because Starlette may dispatch
  to thread-pool workers for sync routes alongside the async event loop.
"""

import logging
import time
from collections.abc import Callable, Awaitable
from threading import Lock
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

API_NAMESPACE = "AshtaChamma/API"

# ──────────────────────────────────────────────────────────────────────────────
# Module-level metric buffers (thread-safe via _lock)
# ──────────────────────────────────────────────────────────────────────────────

_lock = Lock()
_pending_durations: list[float] = []
_request_count: int = 0
_error_5xx_count: int = 0


def _get_cloudwatch_client() -> Any:
    """Return a boto3 CloudWatch client.

    Isolated into a helper so tests can monkeypatch it without touching boto3.
    """
    import boto3  # Late import — only needed at runtime, not import time

    return boto3.client("cloudwatch")


def flush_metrics(cloudwatch_client: Any | None = None) -> None:
    """Drain buffered metrics and publish them to CloudWatch.

    Intended to be called on a 60-second schedule from the background task in
    ``main.py``.  Safe to call from any thread.

    Args:
        cloudwatch_client: Injected boto3 CloudWatch client (for testing).
            Defaults to a real client created via ``_get_cloudwatch_client()``.
    """
    global _pending_durations, _request_count, _error_5xx_count

    with _lock:
        durations = list(_pending_durations)
        request_count = _request_count
        error_count = _error_5xx_count
        _pending_durations = []
        _request_count = 0
        _error_5xx_count = 0

    if not durations and request_count == 0:
        return  # Nothing to publish

    if cloudwatch_client is None:
        cloudwatch_client = _get_cloudwatch_client()

    metric_data: list[dict[str, Any]] = []

    # Individual latency samples — CloudWatch will compute percentiles server-side
    for duration_ms in durations:
        metric_data.append(
            {
                "MetricName": "api_response_time_ms",
                "Value": duration_ms,
                "Unit": "Milliseconds",
            }
        )

    if request_count > 0:
        metric_data.append(
            {
                "MetricName": "http_request_count",
                "Value": float(request_count),
                "Unit": "Count",
            }
        )

    if error_count > 0:
        metric_data.append(
            {
                "MetricName": "http_5xx_count",
                "Value": float(error_count),
                "Unit": "Count",
            }
        )

    # CloudWatch accepts up to 1000 data points per put_metric_data call
    _publish_in_chunks(cloudwatch_client, metric_data)


def _publish_in_chunks(
    cloudwatch_client: Any, metric_data: list[dict[str, Any]], chunk_size: int = 20
) -> None:
    """Publish metric data in chunks respecting CloudWatch API limits.

    Args:
        cloudwatch_client: boto3 CloudWatch client.
        metric_data: List of CloudWatch MetricDatum dicts.
        chunk_size: Number of data points per API call (max 1000, 20 is safe).
    """
    from botocore.exceptions import BotoCoreError, ClientError  # noqa: PLC0415

    for i in range(0, len(metric_data), chunk_size):
        chunk = metric_data[i : i + chunk_size]
        try:
            cloudwatch_client.put_metric_data(
                Namespace=API_NAMESPACE,
                MetricData=chunk,
            )
        except (BotoCoreError, ClientError) as exc:
            # Never let observability code break the application
            logger.warning("Failed to publish API metrics to CloudWatch: %s", exc)


class MetricsMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that measures HTTP request duration and error rates.

    Appends a duration sample and increments counters on every request.
    The actual CloudWatch publication is deferred to the 60-second flush cycle
    so that no individual request incurs an AWS API call.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        global _request_count, _error_5xx_count

        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1_000.0

        with _lock:
            _pending_durations.append(elapsed_ms)
            _request_count += 1
            if response.status_code >= 500:
                _error_5xx_count += 1

        return response
