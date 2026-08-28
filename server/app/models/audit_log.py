"""SQLAlchemy model for the audit_logs table.

Audit logs are append-only — once written they cannot be modified or deleted.
Immutability is enforced at two layers:
  1. ORM layer: SQLAlchemy event listeners raise RuntimeError on any
     before_update or before_delete signal, preventing accidental mutations
     from application code.
  2. Database layer (production): A PostgreSQL trigger should be added via
     Alembic to enforce the same constraint at the DB level.

SOC 2 compliance requires these records to be retained for at least 1 year.
No automated purge or TTL policy must ever be applied to this table.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Immutable audit trail record.

    Each row represents a single audited event. PII must be minimized —
    store user IDs (e.g. Clerk actor_id), not names or email addresses.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    # actor_id is nullable to support system-initiated events (e.g. room.auto_closed)
    # Must be a user ID, never an email or display name.
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Machine-readable event identifier, e.g. "auth.login", "game.capture"
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # The resource type the event was performed on, e.g. "room", "user"
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # The resource identifier, e.g. a room UUID
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Contextual details as JSONB. PII must be minimized — log codes and IDs,
    # never names, emails, or other PII in this field.
    # Attribute named log_metadata to avoid shadowing DeclarativeBase.metadata.
    log_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        # Supports efficient filtering by action + time range for audit queries
        Index("ix_audit_logs_action_created_at", "action", "created_at"),
    )


# ---------------------------------------------------------------------------
# Append-only enforcement at the ORM layer
#
# These listeners fire before SQLAlchemy flushes any UPDATE or DELETE for
# AuditLog instances.  Raising here causes the entire flush to abort, so no
# mutation can accidentally reach the database from application code.
#
# A complementary PostgreSQL trigger should be applied in production Alembic
# migrations to enforce the same constraint at the database level for any
# direct SQL access (e.g. psql sessions, DBA scripts).
# ---------------------------------------------------------------------------


@listens_for(AuditLog, "before_update")
def _prevent_update(mapper: Any, connection: Any, target: "AuditLog") -> None:
    """Raise before any UPDATE reaches the database for an AuditLog row."""
    raise RuntimeError(
        "audit_logs are immutable: UPDATE operations are not permitted. "
        "SOC 2 compliance requires append-only audit records."
    )


@listens_for(AuditLog, "before_delete")
def _prevent_delete(mapper: Any, connection: Any, target: "AuditLog") -> None:
    """Raise before any DELETE reaches the database for an AuditLog row."""
    raise RuntimeError(
        "audit_logs are immutable: DELETE operations are not permitted. "
        "SOC 2 compliance requires audit records to be retained for at least 1 year."
    )
