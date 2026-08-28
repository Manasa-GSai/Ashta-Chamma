"""FastAPI application entry point.

Creates the ``app`` instance, registers all API routers, and manages the
application lifespan (startup / shutdown hooks).

Lifespan responsibilities:
- Initialise the Redis connection pool from ``REDIS_URL`` env var.
- Close the pool cleanly on shutdown to release ElastiCache connections.

REDIS_URL must be provided via the environment (injected from AWS Secrets
Manager at container start). It defaults to a local Redis instance for
development convenience only.
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.redis as redis_module
from app import __version__
from app.redis import RedisManager
from app.routes.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown lifecycle for shared resources.

    On startup the Redis pool is initialised; on shutdown it is closed.
    Failures during Redis initialisation are non-fatal — the application
    continues without caching (see RedisManager.initialize).
    """
    # ---- startup ----
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    manager = RedisManager(redis_url)
    await manager.initialize()
    # Store the live manager in the module-level singleton so all routers and
    # services that import `app.redis.redis_manager` see the same instance.
    redis_module.redis_manager = manager
    logger.info(
        "Application startup complete (version=%s, redis_connected=%s)",
        __version__,
        manager.is_connected,
    )

    yield

    # ---- shutdown ----
    if redis_module.redis_manager is not None:
        await redis_module.redis_manager.close()
        redis_module.redis_manager = None
    logger.info("Application shutdown complete")


app = FastAPI(
    title="Ashta Chamma 3D API",
    description="Backend API for the Ashta Chamma 3D multiplayer board game.",
    version=__version__,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(health_router, prefix="/api")
