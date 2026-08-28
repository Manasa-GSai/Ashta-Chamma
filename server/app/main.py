"""FastAPI application entry point.

Registers all routers and exposes the ASGI application object for uvicorn.
"""

from fastapi import FastAPI

from app.routes import rooms

app = FastAPI(
    title="Ashta Chamma 3D API",
    version="0.1.0",
    description="Server-authoritative backend for the Ashta Chamma 3D board game.",
)

app.include_router(rooms.router)


@app.get("/api/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — returns service version."""
    return {"status": "ok", "version": "0.1.0"}
