"""User-related REST endpoints.

DELETE /api/users/me  —  GDPR right-to-erasure
    Anonymises all PII for the authenticated user, de-links game scores,
    and records a permanent audit log entry.  Returns 204 on success.

The operation is atomic: the caller's ``AsyncSession`` wraps all mutations
inside a single ``BEGIN`` / ``COMMIT`` block.  A failure in any step rolls
back the entire transaction, leaving the database unchanged.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_clerk_id
from app.services.user_service import UserNotFoundError, UserService

router = APIRouter(prefix="/api/users", tags=["users"])


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="GDPR right-to-erasure — delete the authenticated user's personal data",
    responses={
        204: {"description": "User PII successfully erased"},
        401: {"description": "Missing or invalid authentication token"},
        404: {"description": "Authenticated user not found (already erased or never created)"},
    },
)
async def delete_current_user(
    clerk_user_id: str = Depends(get_current_clerk_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Erase the authenticated user's personal data.

    All mutations (user record anonymisation, game_scores de-linking, audit
    log creation) are wrapped in a single database transaction.  Either all
    PII is erased or none is — partial erasure is not possible.

    After successful erasure, subsequent requests with the same JWT will
    return 404 because the stored ``clerk_id`` has been replaced with a hash
    that no longer matches the JWT ``sub`` claim.
    """
    service = UserService(db)
    try:
        async with db.begin():
            await service.erase_user(clerk_user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
