"""FastAPI application entry point.

Creates the :class:`~fastapi.FastAPI` instance and registers all routers.
Uvicorn (or any ASGI server) imports this module via:

    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.routes.users import router as users_router

app = FastAPI(
    title="Ashta Chamma 3D API",
    version="0.1.0",
    description="REST API for the Ashta Chamma 3D multiplayer board game.",
)

# All routes are versioned under /api to allow future v2 co-existence.
app.include_router(users_router, prefix="/api")
