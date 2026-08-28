"""FastAPI application entry point with Sentry error tracking.

Sentry is initialised before the application is constructed so that every
unhandled exception — including those raised during startup — is captured.
When ``SENTRY_DSN`` is absent (local development), initialisation is skipped
entirely and no network traffic is sent to Sentry.
"""

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.config import settings

# Initialise Sentry as early as possible so middleware and startup hooks are
# covered. An empty DSN short-circuits the call — no SDK overhead in dev.
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        integrations=[
            # StarletteIntegration adds request context (URL, method, headers)
            # to every captured event automatically.
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        # PII guard: never attach user email or display name to Sentry events.
        # Only user ID is attached — see AuthMiddleware for context enrichment.
        send_default_pii=False,
    )

app = FastAPI(title="Ashta Chamma 3D API", version="0.1.0")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Capture unhandled exceptions and return a safe 500 response.

    The Sentry event ID is intentionally absent from the response body.
    Leaking it would disclose that Sentry is in use and could assist
    reconnaissance. Clients receive only a generic error message.
    """
    # Explicitly capture in case the Sentry ASGI middleware did not intercept
    # this path (e.g. exceptions raised inside other exception handlers).
    sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Health check endpoint used by ALB and ECS container health probes."""
    return {"status": "ok", "version": "0.1.0"}
