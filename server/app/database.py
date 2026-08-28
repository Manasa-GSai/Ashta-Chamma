"""Database engine and session factory for async SQLAlchemy access.

The session is provided to route handlers via the ``get_db`` FastAPI
dependency.  Each request receives its own ``AsyncSession`` that is closed
after the response is sent.
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

_DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ashta_chamma",
)

engine = create_async_engine(_DATABASE_URL, echo=False, future=True)

_async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    async with _async_session_factory() as session:
        yield session
