"""Tests for RedisManager — connection pooling, cache CRUD, pub/sub, and graceful degradation.

All Redis I/O is mocked via ``unittest.mock`` so the test suite runs without
a live Redis instance or the ``fakeredis`` package.  Behaviour verified:

- Happy-path set / get / delete
- TTL is forwarded to ``SETEX``
- Cache-key namespacing (``ashta:cache:`` prefix)
- Graceful ``None`` / ``False`` return on ``ConnectionError``
- TLS flag set when URL starts with ``rediss://``
- ``MAX_POOL_CONNECTIONS`` forwarded to the pool factory
- Pub/sub publish and subscribe message delivery
- Ping health-check
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.redis import CACHE_KEY_PREFIX, MAX_POOL_CONNECTIONS, RedisManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_redis_client(*, ping_ok: bool = True) -> MagicMock:
    """Return a mock ``redis.asyncio.Redis``-like object."""
    client = MagicMock()
    client.ping = AsyncMock(return_value=ping_ok)
    client.set = AsyncMock(return_value=True)
    client.setex = AsyncMock(return_value=True)
    client.get = AsyncMock(return_value=None)
    client.delete = AsyncMock(return_value=1)
    client.publish = AsyncMock(return_value=1)
    client.aclose = AsyncMock()
    client.pubsub = MagicMock()
    return client


def _make_manager_with_client(client: MagicMock | None = None) -> tuple[RedisManager, MagicMock]:
    """Return a ``(manager, mock_client)`` pair with ``_client`` already set."""
    if client is None:
        client = _make_redis_client()
    manager = RedisManager("redis://localhost:6379")
    manager._client = client  # type: ignore[assignment]
    manager._is_connected = True
    return manager, client


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestRedisManagerInitialize:
    async def test_successful_connection_sets_is_connected(self) -> None:
        mock_client = _make_redis_client(ping_ok=True)
        with (
            patch("app.redis.aioredis.ConnectionPool.from_url") as mock_pool,
            patch("app.redis.aioredis.Redis", return_value=mock_client),
        ):
            mock_pool.return_value = MagicMock()
            manager = RedisManager("redis://localhost:6379")
            await manager.initialize()

        assert manager.is_connected is True

    async def test_connection_error_leaves_manager_degraded(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        mock_client = _make_redis_client()
        mock_client.ping = AsyncMock(side_effect=RedisConnectionError("refused"))

        with (
            patch("app.redis.aioredis.ConnectionPool.from_url") as mock_pool,
            patch("app.redis.aioredis.Redis", return_value=mock_client),
        ):
            mock_pool.return_value = MagicMock()
            manager = RedisManager("redis://unreachable:6379")
            # Must NOT raise — graceful degradation
            await manager.initialize()

        assert manager.is_connected is False

    async def test_ssl_enabled_for_rediss_url(self) -> None:
        mock_client = _make_redis_client()
        with (
            patch("app.redis.aioredis.ConnectionPool.from_url") as mock_pool,
            patch("app.redis.aioredis.Redis", return_value=mock_client),
        ):
            mock_pool.return_value = MagicMock()
            manager = RedisManager("rediss://secure.cache.amazonaws.com:6380")
            await manager.initialize()

        assert mock_pool.call_args.kwargs["ssl"] is True

    async def test_ssl_disabled_for_plain_redis_url(self) -> None:
        mock_client = _make_redis_client()
        with (
            patch("app.redis.aioredis.ConnectionPool.from_url") as mock_pool,
            patch("app.redis.aioredis.Redis", return_value=mock_client),
        ):
            mock_pool.return_value = MagicMock()
            manager = RedisManager("redis://localhost:6379")
            await manager.initialize()

        assert mock_pool.call_args.kwargs["ssl"] is False

    async def test_max_connections_matches_constant(self) -> None:
        mock_client = _make_redis_client()
        with (
            patch("app.redis.aioredis.ConnectionPool.from_url") as mock_pool,
            patch("app.redis.aioredis.Redis", return_value=mock_client),
        ):
            mock_pool.return_value = MagicMock()
            manager = RedisManager("redis://localhost:6379")
            await manager.initialize()

        assert mock_pool.call_args.kwargs["max_connections"] == MAX_POOL_CONNECTIONS
        assert MAX_POOL_CONNECTIONS == 10

    async def test_close_calls_aclose_and_clears_flag(self) -> None:
        manager, client = _make_manager_with_client()
        await manager.close()

        client.aclose.assert_awaited_once()
        assert manager.is_connected is False


# ---------------------------------------------------------------------------
# cache.set
# ---------------------------------------------------------------------------


class TestCacheSet:
    async def test_set_with_ttl_calls_setex(self) -> None:
        manager, client = _make_manager_with_client()
        result = await manager.set("my-key", {"score": 42}, ttl_seconds=60)

        assert result is True
        client.setex.assert_awaited_once_with(
            f"{CACHE_KEY_PREFIX}my-key", 60, json.dumps({"score": 42})
        )
        client.set.assert_not_awaited()

    async def test_set_without_ttl_calls_set(self) -> None:
        manager, client = _make_manager_with_client()
        result = await manager.set("list-key", [1, 2, 3])

        assert result is True
        client.set.assert_awaited_once_with(
            f"{CACHE_KEY_PREFIX}list-key", json.dumps([1, 2, 3])
        )
        client.setex.assert_not_awaited()

    async def test_set_returns_false_when_client_none(self) -> None:
        manager = RedisManager("redis://localhost:6379")
        assert await manager.set("k", "v") is False

    async def test_set_graceful_on_connection_error(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        manager, client = _make_manager_with_client()
        client.setex = AsyncMock(side_effect=RedisConnectionError("dropped"))

        result = await manager.set("k", "v", ttl_seconds=10)

        assert result is False
        assert manager.is_connected is False

    async def test_set_returns_false_for_non_serializable_value(self) -> None:
        manager, _ = _make_manager_with_client()
        # ``object()`` is not JSON-serialisable
        result = await manager.set("k", object())

        assert result is False

    async def test_set_applies_namespace_prefix(self) -> None:
        manager, client = _make_manager_with_client()
        await manager.set("bare-key", "hello", ttl_seconds=5)

        namespaced = client.setex.call_args.args[0]
        assert namespaced.startswith(CACHE_KEY_PREFIX)
        assert namespaced == f"{CACHE_KEY_PREFIX}bare-key"


# ---------------------------------------------------------------------------
# cache.get
# ---------------------------------------------------------------------------


class TestCacheGet:
    async def test_get_returns_deserialised_value(self) -> None:
        manager, client = _make_manager_with_client()
        client.get = AsyncMock(return_value=json.dumps({"a": 1}))

        result = await manager.get("key")

        assert result == {"a": 1}

    async def test_get_returns_none_for_missing_key(self) -> None:
        manager, client = _make_manager_with_client()
        client.get = AsyncMock(return_value=None)

        assert await manager.get("missing") is None

    async def test_get_returns_none_when_client_none(self) -> None:
        manager = RedisManager("redis://localhost:6379")
        assert await manager.get("k") is None

    async def test_get_graceful_on_connection_error(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        manager, client = _make_manager_with_client()
        client.get = AsyncMock(side_effect=RedisConnectionError("dropped"))

        result = await manager.get("k")

        assert result is None
        assert manager.is_connected is False

    async def test_get_returns_none_on_invalid_json(self) -> None:
        manager, client = _make_manager_with_client()
        client.get = AsyncMock(return_value="not-valid-json{{{")

        assert await manager.get("k") is None

    async def test_get_uses_namespace_prefix(self) -> None:
        manager, client = _make_manager_with_client()
        client.get = AsyncMock(return_value=json.dumps("value"))

        await manager.get("foo")

        client.get.assert_awaited_once_with(f"{CACHE_KEY_PREFIX}foo")


# ---------------------------------------------------------------------------
# cache.delete
# ---------------------------------------------------------------------------


class TestCacheDelete:
    async def test_delete_returns_true_when_key_existed(self) -> None:
        manager, client = _make_manager_with_client()
        client.delete = AsyncMock(return_value=1)

        assert await manager.delete("key") is True

    async def test_delete_returns_false_when_key_missing(self) -> None:
        manager, client = _make_manager_with_client()
        client.delete = AsyncMock(return_value=0)

        assert await manager.delete("missing") is False

    async def test_delete_returns_false_when_client_none(self) -> None:
        manager = RedisManager("redis://localhost:6379")
        assert await manager.delete("k") is False

    async def test_delete_graceful_on_connection_error(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        manager, client = _make_manager_with_client()
        client.delete = AsyncMock(side_effect=RedisConnectionError("dropped"))

        assert await manager.delete("k") is False
        assert manager.is_connected is False

    async def test_delete_uses_namespace_prefix(self) -> None:
        manager, client = _make_manager_with_client()

        await manager.delete("bar")

        client.delete.assert_awaited_once_with(f"{CACHE_KEY_PREFIX}bar")


# ---------------------------------------------------------------------------
# Pub/sub — publish
# ---------------------------------------------------------------------------


class TestPublish:
    async def test_publish_sends_serialised_message(self) -> None:
        manager, client = _make_manager_with_client()
        result = await manager.publish("room:abc", {"type": "state_update"})

        assert result is True
        client.publish.assert_awaited_once_with(
            "room:abc", json.dumps({"type": "state_update"})
        )

    async def test_publish_returns_false_when_client_none(self) -> None:
        manager = RedisManager("redis://localhost:6379")
        assert await manager.publish("ch", "msg") is False

    async def test_publish_graceful_on_connection_error(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        manager, client = _make_manager_with_client()
        client.publish = AsyncMock(side_effect=RedisConnectionError("dropped"))

        assert await manager.publish("ch", "msg") is False
        assert manager.is_connected is False

    async def test_publish_returns_false_for_non_serializable_message(self) -> None:
        manager, _ = _make_manager_with_client()
        assert await manager.publish("ch", object()) is False


# ---------------------------------------------------------------------------
# Pub/sub — subscribe
# ---------------------------------------------------------------------------


class TestSubscribe:
    async def test_subscribe_invokes_callback_for_each_message(self) -> None:
        manager, client = _make_manager_with_client()

        received: list[tuple[str, Any]] = []

        async def callback(channel: str, data: Any) -> None:
            received.append((channel, data))

        raw_messages = [
            {"type": "subscribe", "channel": "ch", "data": 1},
            {"type": "message", "channel": "ch", "data": json.dumps({"event": "roll"})},
            {"type": "message", "channel": "ch", "data": json.dumps({"event": "move"})},
        ]

        async def fake_listen() -> AsyncGenerator[dict[str, Any], None]:
            for msg in raw_messages:
                yield msg

        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen = fake_listen
        mock_pubsub.close = AsyncMock()
        client.pubsub = MagicMock(return_value=mock_pubsub)

        await manager.subscribe("ch", callback)

        assert len(received) == 2
        assert received[0] == ("ch", {"event": "roll"})
        assert received[1] == ("ch", {"event": "move"})

    async def test_subscribe_skips_non_message_frames(self) -> None:
        manager, client = _make_manager_with_client()
        received: list[Any] = []

        async def callback(channel: str, data: Any) -> None:
            received.append(data)

        async def fake_listen() -> AsyncGenerator[dict[str, Any], None]:
            yield {"type": "subscribe", "channel": "ch", "data": 1}
            yield {"type": "psubscribe", "channel": "ch", "data": 1}

        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen = fake_listen
        mock_pubsub.close = AsyncMock()
        client.pubsub = MagicMock(return_value=mock_pubsub)

        await manager.subscribe("ch", callback)

        assert received == []

    async def test_subscribe_returns_early_when_client_none(self) -> None:
        manager = RedisManager("redis://localhost:6379")
        called = False

        async def callback(channel: str, data: Any) -> None:
            nonlocal called
            called = True

        await manager.subscribe("ch", callback)
        assert not called

    async def test_subscribe_graceful_on_connection_error(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        manager, client = _make_manager_with_client()

        mock_pubsub = MagicMock()
        mock_pubsub.subscribe = AsyncMock(side_effect=RedisConnectionError("dropped"))
        mock_pubsub.close = AsyncMock()
        client.pubsub = MagicMock(return_value=mock_pubsub)

        async def callback(channel: str, data: Any) -> None:
            pass

        # Must NOT raise
        await manager.subscribe("ch", callback)
        assert manager.is_connected is False


# ---------------------------------------------------------------------------
# Ping / health
# ---------------------------------------------------------------------------


class TestPing:
    async def test_ping_returns_true_when_redis_responds(self) -> None:
        manager, client = _make_manager_with_client()
        client.ping = AsyncMock(return_value=True)

        assert await manager.ping() is True
        assert manager.is_connected is True

    async def test_ping_returns_false_when_client_none(self) -> None:
        manager = RedisManager("redis://localhost:6379")
        assert await manager.ping() is False

    async def test_ping_returns_false_on_connection_error(self) -> None:
        from redis.exceptions import ConnectionError as RedisConnectionError

        manager, client = _make_manager_with_client()
        client.ping = AsyncMock(side_effect=RedisConnectionError("refused"))

        result = await manager.ping()

        assert result is False
        assert manager.is_connected is False
