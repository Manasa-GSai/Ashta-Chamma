"""FastAPI application factory for Ashta Chamma 3D backend.

The module exposes a single ``app`` instance that is referenced by the
Uvicorn entrypoint: ``uvicorn app.main:app --reload``.

Routers for rooms, users, scores, and WebSocket endpoints will be mounted
here by subsequent work orders.  For now the app wires in:
* A health-check endpoint (``GET /api/health``).
* Structured JSON error handlers.
* CORS middleware.
"""

import logging
import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ashta Chamma 3D API",
    version=__version__,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite dev server and production CloudFront origin.
# ---------------------------------------------------------------------------

_allowed_origins = [
    o.strip()
    for o in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error"},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["ops"])
async def health() -> dict[str, str]:
    """Liveness probe used by the ECS ALB health check and CI smoke tests."""
    return {"status": "ok", "version": __version__}
