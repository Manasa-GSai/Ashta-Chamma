"""REST endpoints for room lifecycle: create, read, join, leave.

Route handlers are intentionally thin: they parse the request, delegate to
RoomService, and map domain exceptions to HTTP status codes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, get_current_user
from app.core.database import get_db_session
from app.core.redis_client import get_redis
from app.repositories.room_repository import RoomRepository
from app.schemas.room import CreateRoomRequest, CreateRoomResponse, JoinResponse, RoomResponse
from app.services.room_service import (
    AiPersonaNotFoundError,
    PlayerNotInRoomError,
    RoomAlreadyStartedError,
    RoomFullError,
    RoomNotFoundError,
    RoomService,
)

router = APIRouter(prefix="/api/rooms", tags=["rooms"])


# ---------------------------------------------------------------------------
# Dependency: build RoomService with DB + Redis injected
# ---------------------------------------------------------------------------


async def get_room_service(
    db: AsyncSession = Depends(get_db_session),
    redis: Any = Depends(get_redis),
) -> RoomService:
    """Construct a RoomService with a per-request DB session and shared Redis client."""
    repo = RoomRepository(db)
    return RoomService(repo, redis=redis)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=CreateRoomResponse, status_code=status.HTTP_201_CREATED)
async def create_room(
    request: CreateRoomRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> CreateRoomResponse:
    """Create a new game room.

    The authenticated user becomes the host (player_index 0). AI personas are
    optionally pre-filled as specified by ``ai_persona_ids``.
    """
    try:
        return await service.create_room(
            request=request,
            host_user_id=current_user.user_id,
            host_clerk_id=current_user.clerk_id,
            host_display_name=current_user.display_name,
        )
    except AiPersonaNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


@router.get("/{code}", response_model=RoomResponse)
async def get_room(
    code: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> RoomResponse:
    """Return room details including player list and available seats.

    Only room members may retrieve room details (HTTP 403 otherwise).
    """
    try:
        return await service.get_room(code=code, requesting_user_id=current_user.user_id)
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/{code}/join", response_model=JoinResponse, status_code=status.HTTP_200_OK)
async def join_room(
    code: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> JoinResponse:
    """Join an existing room.

    Returns the caller's ``player_index`` and assigned ``color``.  HTTP 409
    if the room is full.
    """
    try:
        return await service.join_room(
            code=code,
            user_id=current_user.user_id,
            clerk_id=current_user.clerk_id,
            display_name=current_user.display_name,
        )
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RoomFullError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except RoomAlreadyStartedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.delete("/{code}/leave", status_code=status.HTTP_204_NO_CONTENT)
async def leave_room(
    code: str,
    current_user: CurrentUser = Depends(get_current_user),
    service: RoomService = Depends(get_room_service),
) -> None:
    """Leave a room.  Returns HTTP 204 on success.

    If the caller is the host, the next human player is promoted to host.
    If no humans remain, the room is marked abandoned.
    """
    try:
        await service.leave_room(
            code=code,
            user_id=current_user.user_id,
            clerk_id=current_user.clerk_id,
        )
    except RoomNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PlayerNotInRoomError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
