"""FastAPI application factory for the Ashta Chamma backend.

This module creates and configures the ``FastAPI`` application instance.
It wires all routers, registers lifespan handlers, and is the entry point
for Uvicorn: ``uvicorn app.main:app``.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI

from app.providers.redis import close_redis
from app.routes.websocket import router as websocket_router


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown events."""
    # Nothing to initialise at startup — Redis pool is lazy.
    yield
    # Cleanly drain the Redis connection pool.
    await close_redis()


app = FastAPI(
    title="Ashta Chamma 3D API",
    version="0.1.0",
    description="Real-time multiplayer Ashta Chamma game server.",
    lifespan=_lifespan,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(websocket_router)


# ---------------------------------------------------------------------------
# Utility endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Liveness/readiness health check for the ALB target group."""
    return {"status": "ok", "version": "0.1.0"}
