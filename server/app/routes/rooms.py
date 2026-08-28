"""Room management REST API endpoints.

Provides CRUD operations for game rooms plus the spectate join flow.

Authentication is simplified: callers pass their identity via HTTP headers
(X-User-Id and X-Display-Name) rather than a full JWT.  The architecture
document specifies Clerk JWT validation in the AuthMiddleware; that layer
will replace the header-based approach in production.

Endpoints implemented here:
  POST /api/rooms                   — create a room (WO-014 baseline)
  GET  /api/rooms/{code}            — fetch room details (WO-014 baseline)
  POST /api/rooms/{code}/join       — join as a player (WO-014 baseline)
  POST /api/rooms/{code}/spectate   — join as a spectator (WO-026)
"""

import secrets
import string
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException

from app.models import SpectateResponse
from app.services import room_service

router = APIRouter()

_CODE_ALPHABET = string.ascii_uppercase
_CODE_LENGTH = 6


def _require_user_id(x_user_id: str | None) -> str:
    """Raise 401 when the X-User-Id header is absent."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id


def _coerce_display_name(x_display_name: str | None) -> str:
    return x_display_name or "Anonymous"


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/rooms", status_code=200)
async def create_room(
    x_user_id: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Create a new game room.  Returns the room code."""
    user_id = _require_user_id(x_user_id)
    code = _generate_code()
    room_service.create_room(code, user_id)
    return {"room_id": code, "code": code}


@router.get("/rooms/{code}")
async def get_room(code: str) -> dict[str, Any]:
    """Return room metadata and current member list."""
    room = room_service.get_room(code)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    return {**room, "players": room_service.get_room_players(code)}


@router.post("/rooms/{code}/join")
async def join_room(
    code: str,
    x_user_id: Annotated[str | None, Header()] = None,
    x_display_name: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Join a room as a player.

    Returns the player record on success.  Fails with 404 when the room is
    unknown and 409 when the room is full.
    """
    user_id = _require_user_id(x_user_id)
    display_name = _coerce_display_name(x_display_name)

    room = room_service.get_room(code)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")

    player = room_service.join_room(code, user_id, display_name)
    if player is None:
        raise HTTPException(status_code=409, detail="Room is full")

    return player


@router.post("/rooms/{code}/spectate", response_model=SpectateResponse)
async def spectate_room(
    code: str,
    x_user_id: Annotated[str | None, Header()] = None,
    x_display_name: Annotated[str | None, Header()] = None,
) -> SpectateResponse:
    """Join a room as a spectator.

    Spectators receive all game-state broadcasts via WebSocket but are
    blocked from sending game-action messages (roll_request, select_pawn).
    They do NOT count toward the room's max_players limit.

    Returns 404 when the room code is unknown.
    Returns 409 when the caller is already registered as a player in the room.
    """
    user_id = _require_user_id(x_user_id)
    display_name = _coerce_display_name(x_display_name)

    result = room_service.spectate_room(code, user_id, display_name)
    if result is None:
        room = room_service.get_room(code)
        if room is None:
            raise HTTPException(status_code=404, detail="Room not found")
        raise HTTPException(
            status_code=409,
            detail="User is already a player in this room and cannot also spectate",
        )

    return SpectateResponse(**result)
