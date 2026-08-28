"""Redis connection manager for JWKS key caching and session data.

Environment variables expected at runtime:
  REDIS_URL — Redis DSN, e.g. ``redis://localhost:6379/0``
              or ``rediss://...`` for TLS-encrypted connections.

The client is created lazily so tests can inject a fake Redis instance.
"""

import os
from typing import Any

import redis.asyncio as aioredis

_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]


def get_redis_client() -> "aioredis.Redis[Any]":
    """Return the module-level async Redis client, creating it on first call.

    This uses a connection pool internally; callers do not need to manage
    individual connections.
    """
    global _redis_client
    if _redis_client is None:
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = aioredis.from_url(
            redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


def set_redis_client(client: "aioredis.Redis[Any]") -> None:
    """Override the module-level Redis client.

    Intended for use in tests so a ``fakeredis`` instance can be injected
    without patching environment variables.
    """
    global _redis_client
    _redis_client = client


async def get_redis() -> "aioredis.Redis[Any]":  # type: ignore[return]
    """FastAPI dependency that yields the Redis client.

    Usage in a route::

        @router.get("/example")
        async def example(redis = Depends(get_redis)):
            ...
    """
    yield get_redis_client()
