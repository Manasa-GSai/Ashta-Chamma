"""Database session management and FastAPI dependency.

A single async SQLAlchemy engine is created at import time from the
``DATABASE_URL`` environment variable.  The ``get_db`` generator yields
one :class:`AsyncSession` per request and commits or rolls back on exit.
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# asyncpg is the async PostgreSQL driver; the URL must use the
# ``postgresql+asyncpg`` scheme.
_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost/ashta_chamma",
)

engine = create_async_engine(_DATABASE_URL, echo=False, future=True)

_AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for the duration of a request.

    Commits on clean exit; rolls back and re-raises on any exception.
    """
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
