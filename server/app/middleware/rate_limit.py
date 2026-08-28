"""Redis-backed sliding window rate limiting middleware for REST endpoints.

Limits authenticated users to 100 requests/minute.  The sliding window is
implemented using a Redis sorted set (ZSET) keyed by user_id (or client IP
for unauthenticated callers).  The health check endpoint is intentionally
exempt so ECS/ALB health probes are never blocked.

Rate limit state lives in Redis (not in-process memory) so the limit is
shared across all ECS Fargate tasks as required by the architecture.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Paths that bypass rate limiting entirely (health probes, etc.)
_EXEMPT_PATHS: frozenset[str] = frozenset({"/api/health", "/health"})

# Sliding window configuration
_WINDOW_SECONDS: int = 60
_MAX_REQUESTS: int = 100


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter backed by Redis sorted sets.

    Each user's requests are stored in a ZSET with the request timestamp as
    both member and score.  On each request the middleware:
      1. Removes entries outside the window (ZREMRANGEBYSCORE)
      2. Adds the current timestamp (ZADD)
      3. Counts remaining entries (ZCARD)
      4. Resets the key TTL (EXPIRE)

    If *redis_client* is ``None`` (no Redis configured), rate limiting is
    disabled gracefully so development and unit-test environments are not
    affected.
    """

    def __init__(self, app: ASGIApp, redis_client: Any = None) -> None:
        super().__init__(app)
        self._redis = redis_client

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Health check and other exempt endpoints bypass rate limiting.
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # When Redis is not configured, pass through without limiting.
        if self._redis is None:
            return await call_next(request)

        # Prefer a user_id injected by the auth middleware; fall back to IP.
        user_id: str = getattr(request.state, "user_id", None) or _client_ip(request)
        key = f"rate_limit:{user_id}"
        now = time.time()
        window_start = now - _WINDOW_SECONDS

        try:
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now): now})
            pipe.zcard(key)
            pipe.expire(key, _WINDOW_SECONDS + 1)
            results = await pipe.execute()
            request_count: int = results[2]  # zcard result

            if request_count > _MAX_REQUESTS:
                logger.warning(
                    "Rate limit exceeded for user=%s path=%s",
                    user_id,
                    request.url.path,
                )
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again in 60 seconds."},
                    headers={"Retry-After": str(_WINDOW_SECONDS)},
                )
        except Exception:
            # Fail open: if Redis is unavailable, let the request through rather
            # than returning errors for all users.
            logger.exception("Redis error in rate limit middleware; skipping rate check")

        return await call_next(request)


def _client_ip(request: Request) -> str:
    """Return the client IP address, falling back to 'unknown' if unavailable."""
    return request.client.host if request.client else "unknown"
