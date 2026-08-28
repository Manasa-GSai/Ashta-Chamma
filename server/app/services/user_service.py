"""UserService — business logic for user account management.

The primary public operation in this module is ``UserService.erase_user``,
which performs GDPR right-to-erasure (Article 17) for an authenticated user.
"""

import asyncio
import hashlib
import http.client
import logging
import os
import urllib.parse
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)

_CLERK_SECRET_KEY: str = os.environ.get("CLERK_SECRET_KEY", "")
_CLERK_API_HOST: str = "api.clerk.com"


class UserNotFoundError(Exception):
    """Raised when a user lookup by clerk_id returns no results."""


class UserService:
    """Coordinates user-related business operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UserRepository(session)

    async def erase_user(self, clerk_id: str) -> None:
        """Cryptographically erase a user's PII per GDPR Article 17.

        The following mutations are applied within the caller's transaction:

        1. ``display_name`` → ``'Deleted User'``
        2. ``clerk_id`` → SHA-256 hex digest of the original value
        3. ``avatar_url`` → ``NULL``
        4. ``updated_at`` → current UTC timestamp
        5. All ``game_scores`` rows linked to this user have ``user_id`` set
           to ``NULL`` (scores retained for aggregate statistics).
        6. An ``audit_logs`` entry is created with ``action='user.erased'``
           and ``event_metadata`` containing the anonymised user UUID.

        Audit log entries are **intentionally excluded** from the erasure —
        they are exempt under GDPR Article 17(3)(b) as records required for
        compliance with a legal obligation.

        After the local mutations are flushed the Clerk account is deactivated
        asynchronously.  Clerk API failures are logged but do **not** roll
        back the local PII erasure.

        Raises:
            UserNotFoundError: if no user with the given ``clerk_id`` exists.
        """
        user = await self._repo.get_by_clerk_id(clerk_id)
        if user is None:
            raise UserNotFoundError(
                f"No user found with clerk_id={clerk_id!r}. "
                "The user may already have been erased or never existed."
            )

        original_id: uuid.UUID = user.id
        anonymized_clerk_id: str = _sha256_hex(clerk_id)

        # Step 1-4: anonymise all PII columns in a single assignment block.
        user.display_name = "Deleted User"
        user.clerk_id = anonymized_clerk_id
        user.avatar_url = None
        user.updated_at = datetime.now(UTC)

        # Step 5: de-link game scores (retain rows for aggregate statistics).
        await self._repo.nullify_game_scores(original_id)

        # Step 6: create a permanent, immutable audit trail.
        audit_entry = AuditLog(
            actor_id=str(original_id),
            action="user.erased",
            entity_type="user",
            entity_id=str(original_id),
            event_metadata={"anonymized_user_id": str(original_id)},
        )
        self._session.add(audit_entry)

        # Flush so every change is visible within the caller's transaction
        # boundary before the transaction commits.
        await self._session.flush()

        # Best-effort: deactivate the Clerk account.  Runs *after* the local
        # flush so a Clerk failure never prevents local PII erasure.
        # The outer try/except ensures that even an unexpected error from
        # _deactivate_clerk_account (e.g. a test mock raising) cannot roll
        # back a successfully flushed erasure.
        try:
            await _deactivate_clerk_account(clerk_id)
        except Exception:
            logger.warning(
                "Unexpected error during Clerk deactivation for clerk_user_id=%r; "
                "local PII erasure was already flushed successfully.",
                clerk_id,
            )


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _sha256_hex(value: str) -> str:
    """Return the SHA-256 hex digest of ``value`` encoded as UTF-8."""
    return hashlib.sha256(value.encode()).hexdigest()


def _sync_call_clerk_delete(clerk_user_id: str) -> None:
    """Blocking HTTPS call to Clerk's DELETE /v1/users/{id} endpoint.

    Runs in a thread-pool executor so it does not block the event loop.
    """
    if not _CLERK_SECRET_KEY:
        logger.warning(
            "CLERK_SECRET_KEY not configured; skipping Clerk account deactivation "
            "for user_id=%r",
            clerk_user_id,
        )
        return

    path = f"/v1/users/{urllib.parse.quote(clerk_user_id, safe='')}"
    try:
        conn = http.client.HTTPSConnection(_CLERK_API_HOST, timeout=5)
        conn.request(
            "DELETE",
            path,
            headers={"Authorization": f"Bearer {_CLERK_SECRET_KEY}"},
        )
        response = conn.getresponse()
        if response.status not in (200, 204):
            logger.warning(
                "Clerk account deletion returned unexpected HTTP %s for clerk_user_id=%r",
                response.status,
                clerk_user_id,
            )
    except OSError as exc:
        # Network errors must never surface as application errors here —
        # the local PII erasure has already committed.
        logger.exception(
            "Network error while deactivating Clerk account clerk_user_id=%r: %s",
            clerk_user_id,
            exc,
        )
    finally:
        try:
            conn.close()  # type: ignore[union-attr]  # always bound in the try block
        except Exception:
            pass


async def _deactivate_clerk_account(clerk_user_id: str) -> None:
    """Asynchronously deactivate the Clerk account for the erased user.

    Failures are logged but deliberately swallowed — Clerk deactivation is a
    best-effort complement to the local PII erasure, not a prerequisite for it.
    """
    loop = asyncio.get_event_loop()
    try:
        await loop.run_in_executor(None, _sync_call_clerk_delete, clerk_user_id)
    except Exception as exc:
        logger.exception(
            "Unexpected error during Clerk deactivation for clerk_user_id=%r: %s",
            clerk_user_id,
            exc,
        )
