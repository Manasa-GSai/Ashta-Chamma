"""Redis connection manager for caching and pub/sub.

Provides a RedisManager singleton with:
- Connection pooling (max 10 connections, configurable via MAX_POOL_CONNECTIONS)
- JSON-serialized cache get/set/delete with optional TTL
- Pub/sub publish/subscribe helpers for cross-task fan-out
- Graceful degradation: all operations catch RedisConnectionError and return
  None/False rather than propagating to callers — the application continues
  to work even when Redis is temporarily unavailable.

TLS is automatically enabled when REDIS_URL starts with ``rediss://``
(ElastiCache in-transit encryption). The auth token comes exclusively from the
REDIS_URL environment variable, which must be populated from Secrets Manager.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# Cache key namespace — prepended to every key to avoid collisions with other
# consumers of the same Redis instance.
CACHE_KEY_PREFIX = "ashta:cache:"

# Maximum number of idle connections kept in the pool.  Low enough to avoid
# exhausting ElastiCache's connection limit on a small instance.
MAX_POOL_CONNECTIONS = 10


class RedisManager:
    """Async Redis client with connection pooling, JSON caching, and pub/sub.

    Lifecycle::

        manager = RedisManager(redis_url)
        await manager.initialize()   # call once at application startup
        ...                          # use cache / pub-sub helpers
        await manager.close()        # call once at application shutdown

    All public async methods handle :class:`redis.exceptions.ConnectionError`
    and :class:`redis.exceptions.RedisError` internally — callers never
    receive an exception from a Redis failure.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._pool: aioredis.ConnectionPool | None = None
        self._client: aioredis.Redis | None = None  # type: ignore[type-arg]
        self._is_connected: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create the connection pool and verify connectivity with PING.

        Logs a warning and sets ``is_connected = False`` if Redis is
        unreachable — the application will continue without caching.
        """
        # Automatically enable TLS for ElastiCache (rediss://) URLs.
        ssl_enabled: bool = self._redis_url.startswith("rediss://")
        try:
            self._pool = aioredis.ConnectionPool.from_url(
                self._redis_url,
                max_connections=MAX_POOL_CONNECTIONS,
                decode_responses=True,
                ssl=ssl_enabled,
            )
            self._client = aioredis.Redis(connection_pool=self._pool)
            await self._client.ping()
            self._is_connected = True
            logger.info("Redis connection established (url=%s, ssl=%s)", self._redis_url, ssl_enabled)
        except (RedisConnectionError, RedisError, OSError) as exc:
            # Non-fatal: continue without Redis; callers will receive None/False.
            logger.warning(
                "Redis unavailable at startup — caching disabled. Reason: %s", exc
            )
            self._is_connected = False

    async def close(self) -> None:
        """Close the Redis client and release all pooled connections."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error closing Redis client: %s", exc)
        self._is_connected = False
        logger.info("Redis connection pool closed")

    @property
    def is_connected(self) -> bool:
        """Return ``True`` if the last Redis operation succeeded."""
        return self._is_connected

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _namespaced(self, key: str) -> str:
        """Return *key* with the application cache prefix applied."""
        return f"{CACHE_KEY_PREFIX}{key}"

    # ------------------------------------------------------------------
    # Cache operations
    # ------------------------------------------------------------------

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        """Store a JSON-serialisable *value* under *key* with an optional TTL.

        Args:
            key: Cache key (the namespace prefix is added automatically).
            value: Any JSON-serialisable object.
            ttl_seconds: Seconds until the entry expires.  ``None`` means no
                expiry.

        Returns:
            ``True`` on success; ``False`` if Redis is unreachable or the
            value cannot be serialised.
        """
        if self._client is None:
            return False
        try:
            serialized = json.dumps(value)
        except (TypeError, ValueError) as exc:
            logger.warning("JSON serialisation failed for key %r: %s", key, exc)
            return False
        try:
            namespaced = self._namespaced(key)
            if ttl_seconds is not None:
                await self._client.setex(namespaced, ttl_seconds, serialized)
            else:
                await self._client.set(namespaced, serialized)
            return True
        except (RedisConnectionError, RedisError) as exc:
            logger.warning("Redis set failed for key %r: %s", key, exc)
            self._is_connected = False
            return False

    async def get(self, key: str) -> Any | None:
        """Retrieve a cached value or ``None`` if expired / missing / unavailable.

        Args:
            key: Cache key (the namespace prefix is added automatically).

        Returns:
            The deserialised Python object, or ``None``.
        """
        if self._client is None:
            return None
        try:
            raw = await self._client.get(self._namespaced(key))
            if raw is None:
                return None
            return json.loads(raw)
        except (RedisConnectionError, RedisError) as exc:
            logger.warning("Redis get failed for key %r: %s", key, exc)
            self._is_connected = False
            return None
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("JSON deserialisation failed for key %r: %s", key, exc)
            return None

    async def delete(self, key: str) -> bool:
        """Remove the cached entry for *key*.

        Returns:
            ``True`` if the key existed and was deleted; ``False`` otherwise or
            on Redis failure.
        """
        if self._client is None:
            return False
        try:
            result = await self._client.delete(self._namespaced(key))
            return bool(result)
        except (RedisConnectionError, RedisError) as exc:
            logger.warning("Redis delete failed for key %r: %s", key, exc)
            self._is_connected = False
            return False

    # ------------------------------------------------------------------
    # Pub/sub helpers
    # ------------------------------------------------------------------

    async def publish(self, channel: str, message: Any) -> bool:
        """Publish a JSON-serialisable *message* to *channel*.

        Used by the PubSubBridge to broadcast game-state deltas to all Fargate
        tasks subscribed to a room channel.

        Returns:
            ``True`` on success; ``False`` if Redis is unreachable or the
            message cannot be serialised.
        """
        if self._client is None:
            return False
        try:
            serialized = json.dumps(message)
        except (TypeError, ValueError) as exc:
            logger.warning("JSON serialisation failed for publish on channel %r: %s", channel, exc)
            return False
        try:
            await self._client.publish(channel, serialized)
            return True
        except (RedisConnectionError, RedisError) as exc:
            logger.warning("Redis publish failed on channel %r: %s", channel, exc)
            self._is_connected = False
            return False

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str, Any], Awaitable[None]],
    ) -> None:
        """Subscribe to *channel* and invoke *callback(channel, data)* per message.

        Intended to be run inside a long-lived background ``asyncio.Task``.
        Exits silently on :class:`~redis.exceptions.ConnectionError` — the
        caller should decide whether to restart the task.

        Args:
            channel: Redis pub/sub channel name.
            callback: Async callable invoked with ``(channel, deserialised_data)``
                for every inbound message.
        """
        if self._client is None:
            logger.warning("Cannot subscribe to %r — Redis client not initialised", channel)
            return
        pubsub = self._client.pubsub()
        try:
            await pubsub.subscribe(channel)
            async for raw_message in self._iter_messages(pubsub):
                try:
                    data: Any = json.loads(raw_message["data"])
                except (json.JSONDecodeError, ValueError):
                    data = raw_message["data"]
                await callback(raw_message["channel"], data)
        except (RedisConnectionError, RedisError) as exc:
            logger.warning("Redis subscription dropped for channel %r: %s", channel, exc)
            self._is_connected = False
        finally:
            try:
                await pubsub.close()
            except Exception:  # noqa: BLE001
                pass

    @staticmethod
    async def _iter_messages(
        pubsub: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Yield only ``message``-type frames from *pubsub.listen()*."""
        async for raw in pubsub.listen():
            if raw["type"] == "message":
                yield raw

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    async def ping(self) -> bool:
        """Send a PING and return ``True`` if Redis responds.

        Updates :attr:`is_connected` based on the result.
        """
        if self._client is None:
            return False
        try:
            result = await self._client.ping()
            self._is_connected = bool(result)
            return self._is_connected
        except (RedisConnectionError, RedisError):
            self._is_connected = False
            return False


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

# Initialised by the FastAPI lifespan in app.main.  Other modules should
# import this name and check for None before use (it is None until lifespan
# startup completes).
redis_manager: RedisManager | None = None
