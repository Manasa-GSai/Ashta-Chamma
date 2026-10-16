"""FastAPI application factory for Ashta Chamma 3D backend.

The ``app`` instance defined here is the entry point for Uvicorn:

    uvicorn main:app --reload --port 8000

All routers are registered in this module so that the import graph is
clear and integration tests can import ``app`` directly.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(
    title="Ashta Chamma 3D API",
    description="Backend API for the Ashta Chamma 3D multiplayer board game.",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Guard against import errors in route modules crashing the whole process.
# The health endpoint must always be reachable for readiness/liveness probes.
try:
    from app.routes.users import router as users_router
    app.include_router(users_router)
except Exception as _router_exc:  # noqa: BLE001
    import traceback as _tb
    _err = _tb.format_exc()
    logging.error("Failed to load users router: %s\n%s", _router_exc, _err)
    # Expose the error at a dedicated endpoint so it is visible without kubectl.
    from fastapi import Response as _Response

    @app.get("/api/_startup-error", include_in_schema=False)
    async def _startup_error() -> _Response:
        return _Response(content=_err, media_type="text/plain")


@app.get("/api/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Health check endpoint used by the ALB target group."""
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Serve the React SPA for all non-API routes.
# Mount order matters: static assets first, then the SPA catch-all last.
# /app/static is populated by the Docker build from client/dist/.
# ---------------------------------------------------------------------------
_STATIC_DIR = Path("/app/static")

if _STATIC_DIR.exists():
    # Serve compiled JS/CSS/images from Vite's assets/ subfolder
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")
    # Serve 3D model files
    if (_STATIC_DIR / "models").exists():
        app.mount("/models", StaticFiles(directory=_STATIC_DIR / "models"), name="models")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:  # noqa: ARG001
        """Catch-all: return index.html so React Router handles client-side navigation."""
        return FileResponse(_STATIC_DIR / "index.html")
