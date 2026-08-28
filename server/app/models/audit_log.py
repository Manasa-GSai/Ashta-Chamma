"""SQLAlchemy ORM model for the ``audit_logs`` table.

Every mutation that touches user data must create an audit log entry to
satisfy SOC 2 policy. The ``actor_id`` always refers to the authenticated
user performing the action; ``metadata`` carries the specific changed
values in a structured format.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    """Immutable audit trail entry for system mutations."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[uuid.UUID] = mapped_column(nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Changed-field snapshot stored as JSONB; exact shape varies by action.
    metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
