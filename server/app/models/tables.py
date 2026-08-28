"""SQLAlchemy 2.x ORM table definitions.

Tables mirror the schema described in the architecture doc:
  users, ai_personas, rooms, room_players, game_scores, audit_logs.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clerk_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AiPersona(Base):
    __tablename__ = "ai_personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty_level: Mapped[str] = mapped_column(String(20), nullable=False)
    strategy_weights: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False)
    host_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="waiting")
    max_players: Mapped[int] = mapped_column(Integer, default=4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    players: Mapped[list[RoomPlayer]] = relationship(
        "RoomPlayer", back_populates="room", lazy="select"
    )


class RoomPlayer(Base):
    __tablename__ = "room_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    ai_persona_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_personas.id"), nullable=True
    )
    player_index: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    room: Mapped[Room] = relationship("Room", back_populates="players")
    user: Mapped[User | None] = relationship("User", foreign_keys=[user_id])
    ai_persona: Mapped[AiPersona | None] = relationship("AiPersona")


class GameScore(Base):
    __tablename__ = "game_scores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    room_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rooms.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    ai_persona_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_position: Mapped[int] = mapped_column(Integer, nullable=False)
    pawns_captured: Mapped[int] = mapped_column(Integer, default=0)
    pawns_lost: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
