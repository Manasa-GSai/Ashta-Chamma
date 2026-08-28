"""Room repository: all DB access for rooms, players, and audit logs.

Contains zero business logic — only parameterised queries and CRUD
operations, per the layered architecture convention.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.room import AiPersona, AuditLog, Room, RoomPlayer, User


class RoomRepository:
    """Database access object for room-related tables."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ------------------------------------------------------------------
    # Room queries
    # ------------------------------------------------------------------

    async def get_room_by_code(self, code: str) -> Room | None:
        """Fetch a room by its case-insensitive code with all players eager-loaded."""
        result = await self._db.execute(
            select(Room)
            .where(Room.code == code.upper())
            .options(
                selectinload(Room.host),
                selectinload(Room.players)
                .selectinload(RoomPlayer.user),
                selectinload(Room.players)
                .selectinload(RoomPlayer.ai_persona),
            )
        )
        return result.scalar_one_or_none()

    async def code_exists(self, code: str) -> bool:
        """Return True if a room with the given code already exists."""
        result = await self._db.execute(
            select(Room.id).where(Room.code == code.upper())
        )
        return result.scalar_one_or_none() is not None

    async def create_room(self, room: Room) -> Room:
        """Persist a new Room row and flush to populate server-generated fields."""
        self._db.add(room)
        await self._db.flush()
        return room

    # ------------------------------------------------------------------
    # Player queries
    # ------------------------------------------------------------------

    async def add_room_player(self, player: RoomPlayer) -> RoomPlayer:
        """Persist a new RoomPlayer row."""
        self._db.add(player)
        await self._db.flush()
        return player

    async def get_room_player(
        self, room_id: uuid.UUID, user_id: uuid.UUID
    ) -> RoomPlayer | None:
        """Return the RoomPlayer entry for a specific user in a room, or None."""
        result = await self._db.execute(
            select(RoomPlayer).where(
                RoomPlayer.room_id == room_id,
                RoomPlayer.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def remove_room_player(
        self, room_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Delete a player entry; returns True if a row was found and deleted."""
        player = await self.get_room_player(room_id, user_id)
        if player is None:
            return False
        await self._db.delete(player)
        await self._db.flush()
        return True

    # ------------------------------------------------------------------
    # AI Persona queries
    # ------------------------------------------------------------------

    async def get_ai_persona(self, persona_id: int) -> AiPersona | None:
        """Return an active AI persona by ID, or None if not found/inactive."""
        result = await self._db.execute(
            select(AiPersona).where(
                AiPersona.id == persona_id,
                AiPersona.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # User queries
    # ------------------------------------------------------------------

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return a user record by primary key."""
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------

    async def create_audit_log(self, log: AuditLog) -> None:
        """Persist an audit log entry."""
        self._db.add(log)
        await self._db.flush()

    # ------------------------------------------------------------------
    # Session management helpers
    # ------------------------------------------------------------------

    async def commit(self) -> None:
        await self._db.commit()

    async def refresh(self, obj: object) -> None:
        await self._db.refresh(obj)  # type: ignore[arg-type]
