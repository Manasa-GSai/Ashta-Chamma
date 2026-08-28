"""Pydantic schemas for room management endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class CreateRoomRequest(BaseModel):
    """Body for POST /api/rooms."""

    max_players: int = Field(ge=2, le=4, description="Total seats (humans + AI), 2–4")
    # Listed as 'ai_persona_ids' in technical spec; accept 'ai_personas' too for API ergonomics
    ai_persona_ids: list[int] = Field(
        default_factory=list,
        description="IDs of AI personas to pre-fill empty seats",
    )


class CreateRoomResponse(BaseModel):
    """Minimal response body for POST /api/rooms (HTTP 201)."""

    room_id: uuid.UUID
    code: str


class PlayerInfo(BaseModel):
    """Summary of a single player slot in a room."""

    player_index: int
    color: str
    display_name: str
    is_ai: bool


class RoomResponse(BaseModel):
    """Full room detail returned by GET /api/rooms/{code}."""

    room_id: uuid.UUID
    code: str
    status: str
    host_display_name: str
    max_players: int
    players: list[PlayerInfo]
    available_seats: int
    created_at: datetime


class JoinResponse(BaseModel):
    """Response body for POST /api/rooms/{code}/join."""

    player_index: int
    color: str
