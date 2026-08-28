"""Redis provider — Protocol interface for the Redis client.

Services depend on this Protocol, not on the concrete Redis library.
This makes the services testable without a real Redis connection.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class RedisProtocol(Protocol):
    """Minimal Redis interface used by game services."""

    async def set(
        self,
        key: str,
        value: str,
        ex: int | None = None,
    ) -> None:
        """Store *value* under *key*, optionally expiring in *ex* seconds."""
        ...

    async def get(self, key: str) -> str | None:
        """Return the value stored under *key*, or None if absent."""
        ...

    async def exists(self, key: str) -> bool:
        """Return True if *key* exists in Redis."""
        ...
