"""FastAPI application entry point for the Ashta Chamma 3D backend.

Middleware registration order matters in Starlette/FastAPI: middleware added
*last* via ``add_middleware`` executes *first* on the request path (LIFO
wrapping).  We register:
  1. SecurityHeadersMiddleware (outermost — added last so it runs first on
     the *response* path, ensuring headers are always present)
  2. RateLimitMiddleware (added first so the security headers wrap its 429
     responses too)

Redis is wired up from the ``REDIS_URL`` environment variable.  If the
variable is absent or the ``redis`` package is not installed, rate limiting
is silently disabled so local development and CI are not broken.
"""

import logging
import os

from fastapi import FastAPI

from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.routes import websocket as ws_module

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ashta Chamma 3D API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    # Disable the default 422 detail schema leak — validation errors are
    # returned with a generic message to avoid leaking internal model details.
)

# ── Middleware (outermost → innermost for requests; reversed for responses) ──

# Rate limiting: registered first so security headers wrap its 429 responses.
_redis_client = None
_redis_url = os.getenv("REDIS_URL")
if _redis_url:
    try:
        import redis.asyncio as aioredis  # type: ignore[import-untyped]

        _redis_client = aioredis.from_url(_redis_url, decode_responses=True)
        logger.info("Rate limiting enabled via Redis: %s", _redis_url)
    except ImportError:
        logger.warning("redis package not installed; rate limiting is disabled")

app.add_middleware(RateLimitMiddleware, redis_client=_redis_client)

# Security headers: registered last so it executes first on the response path,
# guaranteeing headers on all responses including 429 from rate limiting.
app.add_middleware(SecurityHeadersMiddleware)

# ── Routers ──────────────────────────────────────────────────────────────────

app.include_router(ws_module.router)


# ── Health check (exempt from rate limiting) ─────────────────────────────────


@app.get("/api/health", tags=["monitoring"])
async def health_check() -> dict[str, str]:
    """Liveness probe — no auth required, exempt from rate limiting.

    Used by the ECS health check and ALB target group health probe.
    """
    return {"status": "ok", "version": "0.1.0"}
