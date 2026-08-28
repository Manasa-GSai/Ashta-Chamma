"""FastAPI dependency providers for database sessions and Redis clients.

These thin wrappers centralise the injection points so tests can override
them via ``app.dependency_overrides`` without modifying application code.
"""

from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import get_redis as _get_redis_impl
from app.database import get_db_session as _get_db_impl


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async SQLAlchemy session.

    Delegates to ``app.database.get_db_session`` so the connection lifecycle
    (open, commit/rollback, close) is handled consistently.
    """
    async for session in _get_db_impl():
        yield session


async def get_redis() -> AsyncGenerator[Any, None]:
    """Yield the shared async Redis client.

    Delegates to ``app.cache.get_redis`` so callers do not need to import
    from the cache module directly.
    """
    async for client in _get_redis_impl():
        yield client
