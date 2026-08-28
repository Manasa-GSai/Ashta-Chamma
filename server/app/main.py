"""FastAPI application entry point.

Wires together the router, lifespan (background tasks), and the health check.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.core.config import settings
from app.core.redis_client import close_redis, get_redis
from app.routes.rooms import router as rooms_router

logger = logging.getLogger(__name__)


async def _room_expiry_background_task() -> None:
    """Periodically close rooms that have been idle longer than BR-5's 15-minute limit.

    Each iteration fetches rooms whose Redis ``last_activity`` key is older than
    ``room_inactivity_timeout_seconds`` and marks them as ``abandoned`` in PostgreSQL.

    Full implementation requires a DB session factory call inside the loop;
    the structure is in place for that to be added once the session factory is
    accessible here (depends on an application-level DI container — WO-015).
    """
    while True:
        try:
            await asyncio.sleep(settings.room_expiry_check_interval_seconds)
            redis = await get_redis()
            if redis is None:
                continue
            # TODO(WO-015): query DB for active rooms, check Redis last_activity,
            # update status to 'abandoned' for rooms idle > timeout
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unhandled error in room expiry background task")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start background tasks on startup and clean up on shutdown."""
    expiry_task = asyncio.create_task(_room_expiry_background_task())
    try:
        yield
    finally:
        expiry_task.cancel()
        try:
            await expiry_task
        except asyncio.CancelledError:
            pass
        await close_redis()


app = FastAPI(
    title="Ashta Chamma 3D",
    description="Backend API for the Ashta Chamma 3D multiplayer board game",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(rooms_router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Liveness / readiness probe used by the ALB target group health check."""
    return {"status": "ok", "version": "0.1.0"}
