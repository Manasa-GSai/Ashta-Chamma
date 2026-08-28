"""Redis client factory and FastAPI dependency.

Redis stores ephemeral room state (last_activity timestamps, connected players)
per the architecture design. Its absence degrades gracefully — the DB is the
source of truth for persistent data.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

# The redis package may not be present in all environments (e.g. unit tests
# that mock this dependency).  Import lazily so the module can be imported
# without redis installed.
_redis_client: Any = None


async def get_redis() -> Any:
    """Return a shared redis.asyncio.Redis instance, creating it on first call."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis  # type: ignore[import-untyped]

            _redis_client = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        except ImportError:
            # redis package not installed; return None — callers must handle this
            return None
    return _redis_client


async def close_redis() -> None:
    """Close the shared Redis connection (called on application shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
