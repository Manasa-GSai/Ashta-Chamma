"""SQLAlchemy ORM model for the game_scores table.

Each row records a single player's outcome from one completed game.
Both human (user_id set) and AI (ai_persona_id set) players are stored.
The compound index on (user_id, scored_at DESC) supports efficient
leaderboard and history queries.
"""

import datetime

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameScore(Base):
    """Per-player, per-game result row."""

    __tablename__ = "game_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # Exactly one of user_id / ai_persona_id is set; the other is NULL.
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    ai_persona_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_position: Mapped[int] = mapped_column(Integer, nullable=False)
    pawns_captured: Mapped[int] = mapped_column(Integer, nullable=False)
    pawns_lost: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    scored_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Supports per-user history (ORDER BY scored_at DESC) and leaderboard
        # period filtering efficiently.
        Index("ix_game_scores_user_id_scored_at", "user_id", "scored_at"),
    )
