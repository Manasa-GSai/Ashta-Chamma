"""Tests for RateLimitMiddleware.

Verifies sliding window rate limiting:
- HTTP 429 is returned when the per-user request count exceeds the threshold.
- The health check endpoint is exempt.
- When Redis is unavailable (client=None), requests pass through freely.
- The Retry-After header is set on 429 responses.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.rate_limit import RateLimitMiddleware, _MAX_REQUESTS, _WINDOW_SECONDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRedisPipeline:
    """Minimal pipeline stub that returns a configurable request count."""

    def __init__(self, request_count: int) -> None:
        self._count = request_count

    def zremrangebyscore(self, *_: Any) -> None:
        pass

    def zadd(self, *_: Any) -> None:
        pass

    def zcard(self, *_: Any) -> None:
        pass

    def expire(self, *_: Any) -> None:
        pass

    async def execute(self) -> list[Any]:
        # Matches the order: [zremrangebyscore, zadd, zcard, expire]
        return [None, None, self._count, None]


class _FakeRedis:
    """Minimal Redis stub that returns a configurable request count."""

    def __init__(self, request_count: int = 1) -> None:
        self._count = request_count

    def pipeline(self) -> _FakeRedisPipeline:
        return _FakeRedisPipeline(self._count)


def _make_app(redis_client: Any = None) -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RateLimitMiddleware, redis_client=redis_client)

    @test_app.get("/api/test")
    async def _test_endpoint() -> dict[str, str]:
        return {"ok": "true"}

    @test_app.get("/api/health")
    async def _health() -> dict[str, str]:
        return {"status": "ok"}

    return test_app


# ---------------------------------------------------------------------------
# Tests — no Redis (pass-through mode)
# ---------------------------------------------------------------------------


def test_no_redis_passes_request_through() -> None:
    """When redis_client is None, all requests pass through without rate limiting."""
    app = _make_app(redis_client=None)
    client = TestClient(app)
    response = client.get("/api/test")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests — Redis configured, under the limit
# ---------------------------------------------------------------------------


def test_under_limit_returns_200() -> None:
    """A request below the threshold receives a 200 response."""
    app = _make_app(redis_client=_FakeRedis(request_count=_MAX_REQUESTS))
    client = TestClient(app)
    response = client.get("/api/test")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests — Redis configured, over the limit
# ---------------------------------------------------------------------------


def test_over_limit_returns_429() -> None:
    """When the Redis count exceeds _MAX_REQUESTS the middleware returns 429."""
    app = _make_app(redis_client=_FakeRedis(request_count=_MAX_REQUESTS + 1))
    client = TestClient(app)
    response = client.get("/api/test")
    assert response.status_code == 429


def test_429_response_has_retry_after_header() -> None:
    app = _make_app(redis_client=_FakeRedis(request_count=_MAX_REQUESTS + 1))
    client = TestClient(app)
    response = client.get("/api/test")
    assert "retry-after" in response.headers
    assert response.headers["retry-after"] == str(_WINDOW_SECONDS)


def test_429_response_body_contains_detail() -> None:
    app = _make_app(redis_client=_FakeRedis(request_count=_MAX_REQUESTS + 1))
    client = TestClient(app)
    response = client.get("/api/test")
    assert "detail" in response.json()


# ---------------------------------------------------------------------------
# Tests — exempt paths
# ---------------------------------------------------------------------------


def test_health_endpoint_exempt_even_when_over_limit() -> None:
    """The health endpoint bypasses rate limiting so ECS probes are never blocked."""
    # Even with a count well over the limit, /api/health must return 200.
    app = _make_app(redis_client=_FakeRedis(request_count=_MAX_REQUESTS + 999))
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests — Redis failure (fail open)
# ---------------------------------------------------------------------------


def test_redis_exception_allows_request_through() -> None:
    """If Redis raises an exception the middleware fails open (request passes)."""

    class _BrokenRedis:
        def pipeline(self) -> Any:
            raise ConnectionError("Redis is down")

    app = _make_app(redis_client=_BrokenRedis())
    client = TestClient(app)
    response = client.get("/api/test")
    assert response.status_code == 200
