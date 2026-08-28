"""Redis provider for the Ashta Chamma backend.

Maintains a single shared ``redis.asyncio`` connection pool for the process.
All consumers — WebSocket pub/sub, session cache, JWKS cache — share this pool
except for pub/sub subscribers, which must create their own ``pubsub()``
objects (the Redis protocol restricts a subscribed connection to sub/unsub
commands only).

The pool is lazily initialised on first access and torn down via
``close_redis()`` during application shutdown.
"""

from __future__ import annotations

import os

import redis.asyncio as aioredis
from redis.asyncio import Redis

_REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Module-level pool — one per process, shared across coroutines.
_redis_pool: Redis | None = None  # type: ignore[type-arg]


async def get_redis() -> Redis:  # type: ignore[type-arg]
    """Return the shared Redis client, initialising it on first call."""
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = await aioredis.from_url(
            _REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_pool


async def close_redis() -> None:
    """Drain and close the Redis connection pool (call on app shutdown)."""
    global _redis_pool
    if _redis_pool is not None:
        await _redis_pool.aclose()
        _redis_pool = None
