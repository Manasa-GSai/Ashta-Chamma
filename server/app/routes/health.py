"""Health check endpoint.

GET /api/health — returns application health including Redis connectivity
status.  The ALB health check and Docker HEALTHCHECK both hit this path;
it must respond 200 even when Redis is unavailable (the ``redis`` field will
be ``"unavailable"`` rather than ``"connected"``).
"""

from fastapi import APIRouter
from pydantic import BaseModel

import app.redis as redis_module
from app import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Schema for the health check response body."""

    status: str
    version: str
    redis: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return application health including Redis connectivity.

    Redis is pinged on every call so the status reflects real-time
    connectivity rather than the last known state.  The endpoint never
    raises an error — a Redis failure surfaces as ``"unavailable"`` in the
    response body while the HTTP status remains 200.
    """
    redis_status = "unavailable"
    if redis_module.redis_manager is not None:
        is_up = await redis_module.redis_manager.ping()
        redis_status = "connected" if is_up else "unavailable"

    return HealthResponse(
        status="ok",
        version=__version__,
        redis=redis_status,
    )
