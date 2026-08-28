"""ORM models for rooms, players, users, AI personas, and audit logs.

Table layout follows the architecture's database schema section.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    pass


class RoomStatus(str, enum.Enum):
    waiting = "waiting"
    in_progress = "in_progress"
    completed = "completed"
    abandoned = "abandoned"


class DifficultyLevel(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"
    expert = "expert"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    clerk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    room_players: Mapped[list[RoomPlayer]] = relationship(
        "RoomPlayer", back_populates="user", foreign_keys="RoomPlayer.user_id"
    )
    hosted_rooms: Mapped[list[Room]] = relationship("Room", back_populates="host")


class AiPersona(Base):
    __tablename__ = "ai_personas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty_level: Mapped[DifficultyLevel] = mapped_column(
        SAEnum(DifficultyLevel), nullable=False
    )
    strategy_weights: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    room_players: Mapped[list[RoomPlayer]] = relationship(
        "RoomPlayer", back_populates="ai_persona"
    )


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # 6-character alphanumeric code, case-insensitively unique (stored uppercase)
    code: Mapped[str] = mapped_column(String(6), unique=True, nullable=False, index=True)
    host_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    status: Mapped[RoomStatus] = mapped_column(
        SAEnum(RoomStatus), default=RoomStatus.waiting, nullable=False
    )
    max_players: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    host: Mapped[User] = relationship(
        "User", back_populates="hosted_rooms", foreign_keys=[host_user_id]
    )
    players: Mapped[list[RoomPlayer]] = relationship(
        "RoomPlayer",
        back_populates="room",
        lazy="selectin",
    )


class RoomPlayer(Base):
    __tablename__ = "room_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
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
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )

    room: Mapped[Room] = relationship("Room", back_populates="players")
    user: Mapped[User | None] = relationship(
        "User",
        back_populates="room_players",
        foreign_keys=[user_id],
        lazy="selectin",
    )
    ai_persona: Mapped[AiPersona | None] = relationship(
        "AiPersona", back_populates="room_players", lazy="selectin"
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Stores the Clerk ID of the user who performed the action
    actor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
