"""FastAPI application factory for Ashta Chamma 3D backend.

The ``app`` instance defined here is the entry point for Uvicorn:

    uvicorn main:app --reload --port 8000

All routers are registered in this module so that the import graph is
clear and integration tests can import ``app`` directly.
"""

from fastapi import FastAPI

from app.routes.users import router as users_router

app = FastAPI(
    title="Ashta Chamma 3D API",
    description="Backend API for the Ashta Chamma 3D multiplayer board game.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(users_router)


@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint used by the ALB target group."""
    return {"status": "ok", "version": "0.1.0"}
