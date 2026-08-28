"""Async SQLAlchemy engine and session factory.

Environment variables expected at runtime:
  DATABASE_URL — PostgreSQL DSN, e.g.
      ``postgresql+asyncpg://user:pass@host:5432/dbname``

The engine is created lazily via ``get_engine()`` so tests can substitute a
test database URL without monkey-patching at import time.
"""

import os

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the module-level async engine, creating it once on first call."""
    global _engine
    if _engine is None:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise RuntimeError(
                "DATABASE_URL environment variable is not set. "
                "Expected format: postgresql+asyncpg://user:pass@host:5432/dbname"
            )
        _engine = create_async_engine(
            database_url,
            echo=False,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory, creating it once on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db_session() -> AsyncSession:  # type: ignore[return]
    """Async generator that yields a single ``AsyncSession`` per request.

    Usage in a route::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db_session)):
            ...
    """
    factory = get_session_factory()
    async with factory() as session:
        yield session
