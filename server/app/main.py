"""Ashta Chamma 3D — FastAPI application entry point.

This module creates and configures the FastAPI application instance, registers
all API routers with their route tags and descriptions, and sets up OpenAPI
documentation endpoints at /docs (Swagger UI) and /redoc (ReDoc).

Concrete routers (rooms, users, scores, websocket) will be added by subsequent
work orders and plugged in here.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__

# ---------------------------------------------------------------------------
# OpenAPI metadata
# ---------------------------------------------------------------------------
_DESCRIPTION = """
## Ashta Chamma 3D — API

Server-authoritative backend for the 3D multiplayer Ashta Chamma board game.

### Features

- **Room management** — create, join, and leave game rooms.
- **Real-time gameplay** — WebSocket connections with Redis pub/sub fan-out.
- **Leaderboards** — global and time-windowed score rankings.
- **User profiles** — Clerk-authenticated player profiles.

### Authentication

All endpoints except `/api/health` require a valid **Clerk JWT** passed as a
Bearer token in the `Authorization` header:

```
Authorization: Bearer <clerk_jwt>
```

WebSocket connections pass the JWT as a query parameter:

```
wss://api.example.com/ws/rooms/{room_id}?token=<clerk_jwt>
```

### Real-Time Protocol

In-game communication uses a JSON WebSocket protocol with a `type` discriminator
field. See the [architecture documentation](https://github.com/Manasa-GSai/Ashta-Chamma/blob/main/docs/architecture.md)
for the full message catalogue.
"""

_TAGS_METADATA: list[dict[str, str]] = [
    {
        "name": "health",
        "description": "Service health and readiness checks.",
    },
    {
        "name": "rooms",
        "description": (
            "Game room lifecycle operations: create a room, retrieve room details, "
            "join or leave a room."
        ),
    },
    {
        "name": "users",
        "description": "User profile management for authenticated players.",
    },
    {
        "name": "scores",
        "description": "Leaderboard queries and per-user score history.",
    },
    {
        "name": "websocket",
        "description": (
            "Real-time WebSocket endpoint for in-game communication. "
            "Clients connect and exchange JSON messages: "
            "`roll_request`, `select_pawn`, `chat`, `ping` (client→server) and "
            "`state_update`, `roll_result`, `move_options`, `game_over`, `pong` (server→client)."
        ),
    },
]


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns a fully-configured application instance with:
    - OpenAPI docs at /docs (Swagger UI) and /redoc (ReDoc).
    - Health check endpoint at /api/health.
    - Versioned API prefix /api for all REST routes.
    """
    app = FastAPI(
        title="Ashta Chamma 3D",
        description=_DESCRIPTION,
        version=__version__,
        openapi_tags=_TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        license_info={
            "name": "MIT",
            "url": "https://opensource.org/licenses/MIT",
        },
        contact={
            "name": "Ashta Chamma Team",
            "url": "https://github.com/Manasa-GSai/Ashta-Chamma",
        },
    )

    # ------------------------------------------------------------------
    # Health check — no auth required; used by ALB and ECS health checks
    # ------------------------------------------------------------------
    @app.get(
        "/api/health",
        tags=["health"],
        summary="Service health check",
        description=(
            "Returns the service status and current version. "
            "Used by the ALB health check and ECS task health monitoring. "
            "No authentication required."
        ),
        response_description="Service is healthy and accepting requests.",
    )
    async def health_check() -> JSONResponse:
        """Return a simple health status payload."""
        return JSONResponse(
            content={"status": "ok", "version": __version__},
            status_code=200,
        )

    # ------------------------------------------------------------------
    # Future routers will be registered here, for example:
    #
    #   from app.routers.rooms import router as rooms_router
    #   from app.routers.users import router as users_router
    #   from app.routers.scores import router as scores_router
    #   from app.routers.websocket import router as ws_router
    #
    #   app.include_router(rooms_router, prefix="/api", tags=["rooms"])
    #   app.include_router(users_router, prefix="/api", tags=["users"])
    #   app.include_router(scores_router, prefix="/api", tags=["scores"])
    #   app.include_router(ws_router, tags=["websocket"])
    # ------------------------------------------------------------------

    return app


# Module-level application instance consumed by Uvicorn:
#   uvicorn app.main:app --host 0.0.0.0 --port 8000
app = create_app()
