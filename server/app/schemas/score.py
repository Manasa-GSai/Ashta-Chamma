"""Pydantic schemas for score-related API requests and responses.

These models handle both inbound player result data (used when the game
state machine triggers score recording) and outbound leaderboard /
history responses.
"""

import datetime

from pydantic import BaseModel, Field


class PlayerResult(BaseModel):
    """Input schema representing a single player's outcome at game end.

    Exactly one of ``user_id`` or ``ai_persona_id`` must be set; the
    other should be ``None``.
    """

    user_id: str | None = None
    ai_persona_id: int | None = None
    finish_position: int = Field(ge=1, description="Finishing rank — 1 is the winner")
    pawns_captured: int = Field(ge=0, description="Opponent pawns sent back to base")
    pawns_lost: int = Field(ge=0, description="This player's pawns sent back to base")
    duration_seconds: int = Field(ge=0, description="Seconds from game start to finish")


class LeaderboardEntry(BaseModel):
    """A single entry in the public human-player leaderboard."""

    user_id: str
    display_name: str
    total_wins: int
    total_games: int

    model_config = {"from_attributes": True}


class ScoreHistoryEntry(BaseModel):
    """A single game record in a user's personal score history."""

    id: int
    room_id: str
    finish_position: int
    pawns_captured: int
    pawns_lost: int
    duration_seconds: int
    scored_at: datetime.datetime

    model_config = {"from_attributes": True}


class ScoreHistoryResponse(BaseModel):
    """Paginated response for the user score history endpoint."""

    entries: list[ScoreHistoryEntry]
    total: int
    limit: int
    offset: int
