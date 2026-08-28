"""GameScore ORM model — maps to the `game_scores` table in PostgreSQL."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class GameScore(Base):
    """Per-game result record.

    ``user_id`` is nullable so that a user erasure request can de-link the
    score from the deleted account while preserving the aggregate statistics
    row for leaderboard and analytics purposes (GDPR recital 26).
    """

    __tablename__ = "game_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rooms.id"),
        nullable=False,
    )
    # Nullable — set to NULL on user erasure to de-link PII while retaining stats.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    ai_persona_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("ai_personas.id"),
        nullable=True,
    )
    finish_position: Mapped[int] = mapped_column(Integer, nullable=False)
    pawns_captured: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pawns_lost: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
