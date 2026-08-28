"""FastAPI application factory.

Creates and configures the FastAPI app instance, registers all routers,
and exposes ``app`` as the ASGI entry point for Uvicorn::

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.routes.scores import leaderboard_router, user_scores_router

app = FastAPI(
    title="Ashta Chamma 3D — API",
    version="0.1.0",
    description="Backend API for the Ashta Chamma 3D multiplayer game.",
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(leaderboard_router)
app.include_router(user_scores_router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Lightweight liveness probe for ALB health checks."""
    return {"status": "ok", "version": app.version}
