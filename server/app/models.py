"""Pydantic data models for the Ashta Chamma 3D backend.

These models are used for request/response serialization and internal data
representation across routes and services.
"""

from enum import Enum

from pydantic import BaseModel


class RoomStatus(str, Enum):
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class PlayerRole(str, Enum):
    PLAYER = "player"
    SPECTATOR = "spectator"


class SpectateResponse(BaseModel):
    """Response body for a successful spectate request."""

    room_code: str
    user_id: str
    message: str


class ErrorResponse(BaseModel):
    """Generic error envelope used in REST and WebSocket responses."""

    type: str = "error"
    message: str
