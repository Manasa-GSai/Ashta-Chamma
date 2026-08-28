"""SQLAlchemy ORM model for the audit_logs table.

Stores a tamper-evident audit trail of significant system events such as
game completion, user profile changes, and administrative actions.
"""

import datetime

from sqlalchemy import BigInteger, DateTime, Index, Integer, JSON, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Append-only audit trail entry."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # actor_id is the user who triggered the action; NULL for system-generated events.
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Use metadata_ as the Python attribute to avoid shadowing SQLAlchemy's own
    # `metadata` attribute on mapped classes.
    metadata_: Mapped[dict | None] = mapped_column(JSON, nullable=True, name="metadata")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        # Used for time-range audit queries.
        Index("ix_audit_logs_created_at", "created_at"),
    )
