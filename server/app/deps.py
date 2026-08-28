"""FastAPI dependencies for authentication and authorisation.

``get_current_user`` is the primary auth guard.  It:

1. Extracts the ``Authorization: Bearer <token>`` header via
   :class:`~fastapi.security.HTTPBearer`.
2. Decodes and validates the Clerk-issued JWT.
3. Looks up the corresponding :class:`~app.models.user.User` row in
   PostgreSQL.

Full RS256 / JWKS signature verification is owned by WO-008 (Clerk JWT
Verification Middleware).  The stub below decodes the token without
signature verification so that the routes are functional; WO-008 replaces
``_verify_clerk_jwt`` with a production-safe implementation.

Raises ``HTTP 401`` for any authentication failure so that the frontend
receives a consistent, actionable error code.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.user import User

# auto_error=False lets us raise 401 (not 403) when the header is absent.
_bearer_scheme = HTTPBearer(auto_error=False)


def _verify_clerk_jwt(token: str) -> str:
    """Decode a Clerk JWT and return the ``sub`` (clerk_id) claim.

    .. note::
        This stub decodes without verifying the RS256 signature.  WO-008
        replaces this with full JWKS-based verification.  Never rely on
        this stub in production.
    """
    import jwt  # PyJWT — listed in pyproject.toml dependencies

    try:
        claims: dict = jwt.decode(token, options={"verify_signature": False})
    except jwt.DecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    clerk_id: str | None = claims.get("sub")
    if not clerk_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="JWT is missing the 'sub' claim",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return clerk_id


async def get_current_user(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Return the authenticated :class:`User` or raise ``HTTP 401``.

    Used as a FastAPI dependency on all protected endpoints.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    clerk_id = _verify_clerk_jwt(credentials.credentials)

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found. Please complete registration.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user
