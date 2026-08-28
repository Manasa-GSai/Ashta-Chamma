"""FastAPI dependencies shared across route modules.

``get_current_clerk_id`` extracts the Clerk user ID from the JWT ``sub``
claim.  Full RS256 signature verification against Clerk's JWKS endpoint is
an infrastructure concern deferred to a dedicated middleware once the
``CLERK_JWKS_URL`` environment variable is configured.
"""

import base64
import json
import logging

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer()


def _decode_jwt_payload(token: str) -> dict[str, object]:
    """Decode the payload segment of a JWT without verifying the signature.

    JWT segments are Base64URL-encoded without padding.  This function adds
    the required padding back before decoding.

    Raises:
        ValueError: if the token is malformed or the payload is not valid JSON.
    """
    parts = token.split(".")
    if len(parts) != 3:  # noqa: PLR2004
        raise ValueError(f"Malformed JWT: expected 3 dot-separated segments, got {len(parts)}")

    # Base64URL encoding omits ``=`` padding — restore it before decoding.
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    try:
        payload_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(payload_bytes)  # type: ignore[return-value]
    except Exception as exc:
        raise ValueError(f"Unable to decode JWT payload: {exc}") from exc


async def get_current_clerk_id(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> str:
    """FastAPI dependency — returns the Clerk user ID from the Bearer JWT.

    Raises:
        HTTPException(401): if the token is missing, malformed, or has no
            ``sub`` claim.
    """
    try:
        payload = _decode_jwt_payload(credentials.credentials)
    except ValueError as exc:
        logger.debug("JWT decode failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        ) from exc

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is missing the required 'sub' claim",
        )
    return sub
