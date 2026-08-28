"""Database engine and async session factory.

Reads DATABASE_URL from the environment (required in staging/production).
Defaults to a local development connection string for convenience.

Requires ``asyncpg`` at runtime (add to pyproject.toml dependencies):
    asyncpg = "^0.30.0"
"""

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/ashta_chamma",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yield a database session, closing it after use."""
    async with AsyncSessionLocal() as session:
        yield session
