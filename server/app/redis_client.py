"""Shared async Redis client singleton.

A single ``redis.asyncio.Redis`` instance is reused across the application.
Use ``get_redis()`` everywhere — do not instantiate the client directly so
that tests can patch this function with a mock.
"""

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis

from app.config import REDIS_URL

_redis_client: Optional[redis.Redis] = None  # type: ignore[type-arg]


def get_redis() -> redis.Redis:  # type: ignore[type-arg]
    """Return the singleton async Redis client, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection on application shutdown."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
