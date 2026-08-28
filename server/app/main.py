"""FastAPI application entry point for Ashta Chamma 3D.

Initialises the FastAPI app, registers the MetricsMiddleware, mounts routers,
and runs background tasks for periodic CloudWatch metric publishing.

Architecture layer: entry point (creates the ASGI app consumed by uvicorn).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.middleware.metrics import MetricsMiddleware, flush_metrics
from app.routes.websocket import router as websocket_router

logger = logging.getLogger(__name__)

# Standard (60-second) resolution keeps CloudWatch costs within the $100/month budget.
METRIC_FLUSH_INTERVAL_SECONDS = 60

GAME_NAMESPACE = "AshtaChamma/Game"


def _publish_game_metrics(active_rooms: int = 0, connected_players: int = 0) -> None:
    """Publish game-level gauge metrics (point-in-time counts) to CloudWatch.

    These are separate from request-scoped metrics because they represent
    current inventory rather than latency histograms.  Called from the
    background task on the same 60-second cadence.

    Args:
        active_rooms: Number of rooms currently in progress.
        connected_players: Number of WebSocket clients currently connected.
    """
    try:
        import boto3  # noqa: PLC0415 — lazy import to allow test patching
        from botocore.exceptions import BotoCoreError, ClientError  # noqa: PLC0415

        client = boto3.client("cloudwatch")
        client.put_metric_data(
            Namespace=GAME_NAMESPACE,
            MetricData=[
                {
                    "MetricName": "active_rooms_count",
                    "Value": float(active_rooms),
                    "Unit": "Count",
                },
                {
                    "MetricName": "connected_players_count",
                    "Value": float(connected_players),
                    "Unit": "Count",
                },
            ],
        )
    except Exception as exc:  # noqa: BLE001 — observability must not crash the app
        logger.warning("Failed to publish game metrics to CloudWatch: %s", exc)


async def _metrics_background_task() -> None:
    """Flush HTTP metrics and publish game counters every 60 seconds.

    Uses standard (60 s) resolution to stay within the $100/month CloudWatch
    budget.  The coroutine runs indefinitely until cancelled at shutdown.

    Game counters (active rooms, connected players) are stubbed to 0 here;
    once the RoomManager service is implemented (WO-004+) it will be queried
    for live counts.
    """
    while True:
        await asyncio.sleep(METRIC_FLUSH_INTERVAL_SECONDS)
        try:
            flush_metrics()
            # TODO(WO-004): pass real room/player counts from RoomManager
            _publish_game_metrics(active_rooms=0, connected_players=0)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error in metrics background task: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, Any]:
    """Manage application startup/shutdown lifecycle.

    Starts the metrics background task on boot and cancels it cleanly on
    shutdown so the last partial bucket of metrics is not silently discarded.
    (A final flush could be added here if needed.)
    """
    task = asyncio.create_task(_metrics_background_task())
    logger.info("Metrics background task started (flush interval: %ds)", METRIC_FLUSH_INTERVAL_SECONDS)
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        logger.info("Metrics background task stopped")


# ──────────────────────────────────────────────────────────────────────────────
# Application factory
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Ashta Chamma 3D API",
    version="0.1.0",
    description="Backend API for the Ashta Chamma 3D multiplayer board game",
    lifespan=lifespan,
)

# MetricsMiddleware is registered before other middleware so it measures the
# full request duration, including time spent in auth and business logic layers.
app.add_middleware(MetricsMiddleware)

# Routers
app.include_router(websocket_router)


# ──────────────────────────────────────────────────────────────────────────────
# Built-in endpoints
# ──────────────────────────────────────────────────────────────────────────────


@app.get("/api/health", tags=["health"])
async def health_check() -> JSONResponse:
    """Liveness probe used by ALB health checks and ECS container health check."""
    return JSONResponse({"status": "ok", "version": app.version})
