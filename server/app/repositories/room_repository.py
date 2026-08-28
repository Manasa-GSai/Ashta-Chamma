"""Room repository — Protocol interface and SQLAlchemy implementation.

Services depend on RoomRepositoryProtocol, not on SqlRoomRepository.
This keeps the service layer fully testable with simple in-memory fakes.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import RoomStatus
from app.models.tables import AuditLog, Room, RoomPlayer


# ---------------------------------------------------------------------------
# Protocol — the interface the service layer programs against
# ---------------------------------------------------------------------------


@runtime_checkable
class RoomRepositoryProtocol(Protocol):
    """Data-access contract for room and audit-log operations."""

    async def get_room_by_code(self, code: str) -> Room | None:
        """Return a Room row by its short code, or None."""
        ...

    async def get_room_players(self, room_id: uuid.UUID) -> list[RoomPlayer]:
        """Return all RoomPlayer rows for the given room."""
        ...

    async def update_room_started(
        self, room_id: uuid.UUID, started_at: datetime
    ) -> None:
        """Mark the room as 'playing' and record its start timestamp."""
        ...

    async def create_audit_log(
        self,
        actor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any],
    ) -> None:
        """Append an audit log entry."""
        ...


# ---------------------------------------------------------------------------
# SQLAlchemy implementation
# ---------------------------------------------------------------------------


class SqlRoomRepository:
    """Concrete room repository backed by an async SQLAlchemy session."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_room_by_code(self, code: str) -> Room | None:
        result = await self._session.execute(select(Room).where(Room.code == code))
        return result.scalar_one_or_none()

    async def get_room_players(self, room_id: uuid.UUID) -> list[RoomPlayer]:
        result = await self._session.execute(
            select(RoomPlayer).where(RoomPlayer.room_id == room_id)
        )
        return list(result.scalars().all())

    async def update_room_started(
        self, room_id: uuid.UUID, started_at: datetime
    ) -> None:
        await self._session.execute(
            update(Room)
            .where(Room.id == room_id)
            .values(status=RoomStatus.PLAYING.value, started_at=started_at)
        )
        await self._session.flush()

    async def create_audit_log(
        self,
        actor_id: str | None,
        action: str,
        entity_type: str,
        entity_id: str,
        metadata: dict[str, Any],
    ) -> None:
        log = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata,
        )
        self._session.add(log)
        await self._session.flush()
