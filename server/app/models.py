"""SQLAlchemy ORM models for Ashta Chamma 3D.

Defines the ``users`` and ``audit_logs`` tables used by the auth layer.
Additional tables (rooms, room_players, game_scores, ai_personas) will be
added by future work orders that own those domains.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _utcnow() -> datetime:
    """Return the current UTC datetime (timezone-aware)."""
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


class User(Base):
    """Registered player profile synced from Clerk on first login."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # Clerk's external user ID — stable, unique across our system.
    clerk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Locale persisted so the UI can restore the player's language preference.
    locale: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} clerk_id={self.clerk_id!r}>"


class AuditLog(Base):
    """Immutable audit trail for security-relevant events.

    Per the security spec, auth success/failure entries are written here.
    We deliberately avoid storing full PII (e.g. email) in ``metadata``
    to limit the blast radius of a log-table compromise.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # actor_id is the Clerk user ID (or None for unauthenticated failures).
    actor_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    # action is a dot-separated namespace, e.g. "auth.login" or "auth.failed".
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Arbitrary JSONB payload — keep PII out of here.
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} action={self.action!r} actor={self.actor_id!r}>"
