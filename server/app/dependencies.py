"""FastAPI dependency providers for authentication and common resources.

The ``get_current_user_id`` dependency extracts the authenticated user's
ID from the Clerk-issued JWT. Full signature verification (JWKS lookup,
expiry validation) is implemented in WO-008. This module provides the
dependency interface so that route handlers and tests can use a stable
contract without coupling to Clerk SDK details.

Tests override this dependency via ``app.dependency_overrides`` to inject
a known user_id without a real JWT.
"""

import base64
import json
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=True)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """Extract the Clerk user ID (``sub`` claim) from a Bearer JWT.

    This is a **stub** implementation: it decodes the payload without
    verifying the signature so that routes can be exercised without a live
    Clerk environment. WO-008 replaces the decode logic with a full JWKS
    verification.

    Raises:
        HTTPException 401: If the token is missing, malformed, or has no
            ``sub`` claim.
    """
    token = credentials.credentials
    try:
        # JWT structure: <header_b64>.<payload_b64>.<signature_b64>
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Not a three-part JWT")

        payload_b64 = parts[1]
        # Restore standard base64 padding.
        padding_needed = (4 - len(payload_b64) % 4) % 4
        payload_b64 += "=" * padding_needed

        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        user_id: str | None = payload.get("sub")
        if not user_id:
            raise ValueError("JWT payload missing 'sub' claim")
        return user_id
    except Exception as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
