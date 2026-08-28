"""FastAPI application entry point.

The lifespan context manager registers the idle-room cleanup background task
(BR-5) at server startup and cancels it gracefully on shutdown.  All route
routers are also mounted here.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.redis_client import close_redis
from app.routes.websocket import router as ws_router
from app.tasks.cleanup import run_cleanup_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and graceful shutdown.

    On startup: launches the idle-room cleanup task as a background asyncio
    task so it never blocks the event loop.

    On shutdown: cancels the task and closes the Redis connection.
    """
    cleanup_task = asyncio.create_task(run_cleanup_loop(), name="idle_room_cleanup")
    logger.info("Background idle-room cleanup task started.")
    try:
        yield
    finally:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            logger.info("Background idle-room cleanup task stopped.")
        await close_redis()


app = FastAPI(
    title="Ashta Chamma 3D API",
    version="0.1.0",
    description="Server-authoritative backend for the Ashta Chamma 3D game.",
    lifespan=lifespan,
)

app.include_router(ws_router)


@app.get("/api/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe used by the ALB health check."""
    return {"status": "ok", "version": "0.1.0"}
