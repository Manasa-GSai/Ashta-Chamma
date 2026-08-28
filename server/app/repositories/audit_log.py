"""Audit log repository.

Records game and system actions to the ``audit_logs`` PostgreSQL table
(defined in the DB schema: bigserial PK, actor_id, action, entity_type,
entity_id, metadata JSONB, created_at).

This function is intentionally fire-and-forget from the caller's perspective.
Audit failures must never interrupt game flow — they are logged as errors
but the exception is swallowed here so callers do not need to handle it.
"""

from __future__ import annotations

import logging
from typing import Any

_logger = logging.getLogger(__name__)


async def write_audit_log(
    actor_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Persist an audit event to the audit_logs table.

    Parameters
    ----------
    actor_id:
        The ``user_id`` (Clerk ``sub``) of the player who triggered the event.
    action:
        Dot-separated action name, e.g. ``"game.roll"`` or ``"game.move"``.
    entity_type:
        The resource type being acted upon, e.g. ``"room"``.
    entity_id:
        The resource identifier, e.g. the room UUID.
    metadata:
        Optional JSON-serialisable dict with action-specific details.
    """
    record = {
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "metadata": metadata or {},
    }
    try:
        # Structured log — forwarded to CloudWatch in production.
        _logger.info("audit event: %s", record)
        # TODO[WO-DB-001]: INSERT INTO audit_logs via SQLAlchemy async session
    except Exception:
        # Audit must never crash the game loop.
        _logger.exception(
            "Failed to write audit log for action=%s actor=%s",
            action,
            actor_id,
        )
