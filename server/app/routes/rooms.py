"""REST API routes for room management.

Current endpoints
-----------------
POST /api/rooms/{code}/start
    Start the game session for a room. Host-only. Requires ≥ 2 players.
    Returns the initial game state snapshot.

Authentication
--------------
The ``Authorization: Bearer <token>`` header is required. In production
the token is a Clerk JWT validated by auth middleware. For this scope the
bearer token value is used directly as the user identifier; full JWT
validation middleware will be wired in a dedicated auth WO.

Dependency injection
--------------------
``_get_game_service`` raises ``NotImplementedError`` by default and must
be overridden via ``app.dependency_overrides`` at startup (or in tests).
This avoids hidden coupling to a concrete DB or Redis instance.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException

from app.services.game_service import GameService, GameStartError

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


# ---------------------------------------------------------------------------
# Shared dependencies
# ---------------------------------------------------------------------------


async def _require_auth(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract the caller's user ID from the Bearer token.

    Raises 401 when the header is absent or not a Bearer token.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header.",
        )
    return authorization.removeprefix("Bearer ").strip()


async def _get_game_service() -> GameService:
    """Dependency placeholder — must be overridden before the server starts.

    In production this dependency is wired in the FastAPI lifespan to a
    ``GameService`` built with real repository and Redis instances.
    In tests it is replaced via ``app.dependency_overrides``.
    """
    raise NotImplementedError(
        "_get_game_service must be overridden with a real or mock provider."
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/{code}/start", status_code=200)
async def start_game(
    code: str,
    current_user_id: Annotated[str, Depends(_require_auth)],
    game_service: Annotated[GameService, Depends(_get_game_service)],
) -> dict[str, Any]:
    """Start the game for room *code*.

    Only the room host may call this endpoint. At least 2 players must be
    present. Returns the initial game state snapshot for broadcasting.

    Status codes:
        200: Game started successfully.
        400: Fewer than 2 players in the room.
        401: Missing or invalid Authorization header.
        403: Caller is not the room host.
        404: Room not found.
        409: Game is already in progress.
    """
    try:
        snapshot = await game_service.start_game(
            room_code=code,
            requester_id=current_user_id,
        )
    except GameStartError as exc:
        raise HTTPException(status_code=exc.http_status, detail=str(exc)) from exc

    return snapshot
