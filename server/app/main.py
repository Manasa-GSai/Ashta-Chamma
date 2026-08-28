"""FastAPI application entry point.

Mounts all routers and provides the health-check endpoint.
"""

from fastapi import FastAPI

from app.routes import rooms
from app.routes import websocket as ws_routes

app = FastAPI(
    title="Ashta Chamma 3D",
    version="0.1.0",
    description="Real-time multiplayer Ashta Chamma game server",
)

app.include_router(rooms.router, prefix="/api")
app.include_router(ws_routes.router)


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Liveness probe for ALB health checks."""
    return {"status": "ok", "version": "0.1.0"}
