"""User profile endpoints.

Provides:
- ``GET  /api/users/me`` — return the authenticated user's profile.
- ``PUT  /api/users/me`` — update display name and/or locale, audit-logged.

Both endpoints require a valid Clerk JWT (enforced by
:func:`~app.deps.get_current_user`).  The PUT endpoint validates the
request body with Pydantic strict types before touching the database.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import get_current_user
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateRequest

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="Get current user profile")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Return the profile of the currently authenticated user.

    The ``get_current_user`` dependency handles JWT verification and DB
    lookup, so this handler is intentionally thin.
    """
    return current_user


@router.put("/me", response_model=UserResponse, summary="Update current user profile")
async def update_me(
    body: UserUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Update the authenticated user's display name and/or locale.

    Tracks only changed fields in the audit log metadata so the log entry
    is meaningful even when only one of the two fields is modified.  The
    audit entry is written in the same transaction as the user update to
    ensure consistency.
    """
    changed_fields: dict[str, Any] = {}

    if body.display_name != current_user.display_name:
        changed_fields["display_name"] = {
            "from": current_user.display_name,
            "to": body.display_name,
        }
        current_user.display_name = body.display_name

    if body.locale != current_user.locale:
        changed_fields["locale"] = {
            "from": current_user.locale,
            "to": body.locale,
        }
        current_user.locale = body.locale

    db.add(current_user)

    # Audit log is mandatory for every profile mutation (SOC 2 requirement).
    audit_entry = AuditLog(
        actor_id=current_user.id,
        action="user.profile_updated",
        entity_type="user",
        entity_id=str(current_user.id),
        metadata={"changed_fields": changed_fields},
    )
    db.add(audit_entry)

    # Flush within the transaction so the updated values are reflected on
    # the object without waiting for the session commit.
    await db.flush()
    await db.refresh(current_user)

    return current_user
