"""Admin-only REST endpoints.

These endpoints are intended for internal operational use only and MUST NOT
be exposed to end users in production.  Access is controlled by two gates:

1. Feature flag: ADMIN_AUDIT_LOGS_ENABLED env var must be set to "true".
   When disabled, the endpoint returns 404 — it does not reveal its existence.
2. Shared secret: The caller must supply the ADMIN_SECRET env var value as a
   Bearer token.  In production this secret is managed via AWS Secrets Manager
   and injected as an env var at task startup.

GET /api/admin/audit-logs supports filtering by action, entity_type, and
date range.  It never modifies any record — audit logs are read-only here.
"""

import os
from datetime import datetime
from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

router = APIRouter(prefix="/api/admin", tags=["admin"])

_bearer = HTTPBearer(auto_error=False)


def _require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Enforce feature flag + shared-secret gate for admin endpoints.

    Returns None on success; raises HTTPException on any failure.
    Using 404 for a disabled endpoint intentionally avoids leaking
    the endpoint's existence to potential attackers.
    """
    enabled = os.getenv("ADMIN_AUDIT_LOGS_ENABLED", "false").lower() == "true"
    if not enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found",
        )

    admin_secret = os.getenv("ADMIN_SECRET", "")
    if not admin_secret:
        # Secret not configured — fail closed rather than open
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoint not configured",
        )

    token = credentials.credentials if credentials else None
    if token != admin_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )


class AuditLogResponse(BaseModel):
    """Serialised representation of a single audit log entry."""

    id: int
    actor_id: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    # log_metadata is the Python ORM attribute; serialise as "metadata" in JSON
    metadata: dict[str, Any] | None = Field(default=None, validation_alias="log_metadata")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class AuditLogListResponse(BaseModel):
    """Paginated list of audit log entries."""

    items: list[AuditLogResponse]
    total: int
    limit: int
    offset: int


async def get_db() -> AsyncGenerator[AsyncSession, None]:  # type: ignore[return]
    """Database session dependency — placeholder until session factory is wired.

    The concrete implementation will be provided when the async session factory
    is set up as part of the main application factory (see WO-005/WO-016).
    Tests override this dependency directly.
    """
    raise NotImplementedError("Database session factory not wired up yet")
    yield  # type: ignore[misc]  # noqa: unreachable — satisfies generator signature


@router.get(
    "/audit-logs",
    response_model=AuditLogListResponse,
    summary="Query audit logs (admin only)",
    description=(
        "Internal endpoint for querying the immutable audit log. "
        "Requires ADMIN_AUDIT_LOGS_ENABLED=true and a valid Bearer token "
        "matching ADMIN_SECRET.  Supports filtering by action, entity_type, "
        "and an inclusive date range.  Never modifies audit records."
    ),
)
async def get_audit_logs(
    action: str | None = Query(
        None, description="Filter by action, e.g. auth.login"
    ),
    entity_type: str | None = Query(
        None, description="Filter by entity type, e.g. room"
    ),
    date_from: datetime | None = Query(
        None, description="Inclusive range start (ISO 8601 with timezone)"
    ),
    date_to: datetime | None = Query(
        None, description="Inclusive range end (ISO 8601 with timezone)"
    ),
    limit: int = Query(50, ge=1, le=500, description="Max results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: None = Depends(_require_admin),
    session: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Return audit log entries matching the provided filters.

    Results are ordered newest-first.  Use limit + offset for pagination.
    All filters are optional; omitting them returns all entries.
    """
    # Build shared WHERE clause for both the data and count queries
    filters = []
    if action is not None:
        filters.append(AuditLog.action == action)
    if entity_type is not None:
        filters.append(AuditLog.entity_type == entity_type)
    if date_from is not None:
        filters.append(AuditLog.created_at >= date_from)
    if date_to is not None:
        filters.append(AuditLog.created_at <= date_to)

    data_query = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_query = (
        select(func.count())
        .select_from(AuditLog)
        .where(*filters)
    )

    result = await session.execute(data_query)
    rows = result.scalars().all()

    count_result = await session.execute(count_query)
    total = count_result.scalar_one()

    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
