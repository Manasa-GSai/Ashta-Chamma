"""AuditLog ORM model — maps to the `audit_logs` table in PostgreSQL.

Audit log entries are exempt from GDPR right-to-erasure requests under
Article 17(3)(b) as records required to comply with legal obligations.
They must never be deleted as part of a user erasure workflow.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Immutable system audit trail entry."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # actor_id holds the internal user UUID (not the Clerk ID) so that the
    # log entry remains meaningful even after the clerk_id is anonymized.
    actor_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Stored as `event_metadata` in Python to avoid a name clash with
    # SQLAlchemy's own `metadata` class attribute on DeclarativeBase.
    event_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
