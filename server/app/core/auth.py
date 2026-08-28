"""JWT authentication dependency (simplified Clerk integration).

WO-008 will replace the payload extraction below with full RS256 signature
verification against the Clerk JWKS endpoint.  Until then, the JWT payload
is decoded without signature validation — suitable for development and testing
only.  The route tests override this dependency entirely via
``app.dependency_overrides``.
"""

from __future__ import annotations

import base64
import json
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.room import User

bearer_scheme = HTTPBearer()


class CurrentUser:
    """Lightweight identity object injected into route handlers."""

    def __init__(self, clerk_id: str, user_id: uuid.UUID, display_name: str) -> None:
        self.clerk_id = clerk_id
        self.user_id = user_id
        self.display_name = display_name


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db_session),
) -> CurrentUser:
    """Extract and validate the Clerk JWT, then return the authenticated user.

    Signature verification is deferred to WO-008 which wires up the Clerk
    JWKS endpoint.  This version decodes the payload only — never use in
    production without WO-008's verification layer on top.
    """
    token = credentials.credentials
    try:
        parts = token.split(".")
        if len(parts) != 3:  # noqa: PLR2004
            raise ValueError("Not a valid JWT structure")
        payload_b64 = parts[1]
        # Add padding so standard base64 decoder is satisfied
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        clerk_id: str | None = payload.get("sub")
        if not clerk_id:
            raise ValueError("Missing 'sub' claim in JWT payload")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or malformed JWT",
        ) from exc

    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"User with Clerk ID '{clerk_id}' not found. Register first.",
        )

    return CurrentUser(
        clerk_id=user.clerk_id,
        user_id=user.id,
        display_name=user.display_name,
    )
