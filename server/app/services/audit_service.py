"""Centralized audit logging service.

Provides a single entry point — log_action() — for recording all critical
system events into the audit_logs table.  By centralising writes here we:
  - Guarantee a consistent schema for every audit entry.
  - Enforce PII minimisation: callers log user IDs, not names/emails.
  - Make it straightforward to audit coverage across all route handlers.

Call log_action() inside any route or WebSocket handler that performs a
critical action (see CRITICAL_ACTIONS below).  The caller owns the session
lifecycle and must commit; log_action() only flushes to assign the PK.

Async inserts keep audit overhead minimal — the flush is awaited so the
auto-generated id is available to the caller, but the commit is deferred to
the surrounding request transaction.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

# ---------------------------------------------------------------------------
# Canonical list of critical audit event types.
#
# This set is the authoritative checklist used to verify that every
# critical system action has a corresponding audit log call in the codebase.
# Add new events here whenever a new critical action is introduced.
# ---------------------------------------------------------------------------
CRITICAL_ACTIONS: frozenset[str] = frozenset(
    {
        # Authentication events
        "auth.login",
        "auth.failed",
        "auth.logout",
        # User data events
        "user.profile_updated",
        "user.erased",
        # Room lifecycle events
        "room.created",
        "room.joined",
        "room.left",
        "room.auto_closed",
        # In-game events
        "game.started",
        "game.roll",
        "game.move",
        "game.capture",
        "game.completed",
    }
)


async def log_action(
    session: AsyncSession,
    *,
    actor_id: str | None,
    action: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    """Insert a new immutable audit log entry and flush the session.

    Parameters
    ----------
    session:
        An active async SQLAlchemy session.  The caller owns the session
        lifecycle; this function flushes (assigns the PK) but does NOT
        commit — callers must commit their outer transaction.
    actor_id:
        The Clerk user ID of the principal performing the action.
        Pass None for system-initiated events (e.g. room.auto_closed).
        Must NOT contain PII such as email addresses or display names.
    action:
        Machine-readable event identifier in dot-notation, e.g. "auth.login".
        Should be one of CRITICAL_ACTIONS for compliance-covered events.
    entity_type:
        The resource type the action was performed on, e.g. "room", "user".
    entity_id:
        The resource identifier, e.g. a room UUID or user Clerk ID.
    metadata:
        Optional JSONB context blob.  PII must be minimised — store IDs
        and codes, not names, emails, or other personal data.

    Returns
    -------
    AuditLog:
        The newly created (flushed but not committed) log entry.
    """
    entry = AuditLog(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        log_metadata=metadata,
        created_at=datetime.now(tz=timezone.utc),
    )
    session.add(entry)
    # Flush to assign the auto-generated id without committing the transaction.
    await session.flush()
    return entry
