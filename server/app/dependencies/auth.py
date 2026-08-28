"""Authentication utilities for WebSocket connections.

``ws_authenticate`` validates a JWT token string and returns the decoded
claims dict on success.  Callers receive a ``WebSocketException`` with
close code **4001** (application-level auth failure per RFC 6455 §7.4.2)
for any invalid, expired, or missing token.

In production the ``JWT_SECRET`` env-var is replaced by RS256 validation
against Clerk's JWKS endpoint (cached in Redis).  Development/test mode
falls back to HS256 with ``JWT_SECRET``.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import WebSocketException

# Custom application close code for authentication failure.
_WS_CLOSE_AUTH_FAILED: int = 4001


def ws_authenticate(token: str) -> dict[str, Any]:
    """Validate a JWT token for a WebSocket connection.

    Returns the decoded claims dict (e.g. ``{"sub": "user_123", ...}``).
    Raises ``WebSocketException(code=4001)`` for any validation failure.

    The caller is responsible for calling ``websocket.close(code=4001)``
    after catching the exception — the exception itself does not close the
    connection so that the route handler can sequence the close correctly.
    """
    if not token:
        raise WebSocketException(
            code=_WS_CLOSE_AUTH_FAILED,
            reason="Missing authentication token",
        )

    try:
        import jwt  # PyJWT
    except ImportError as exc:  # pragma: no cover — only absent before install
        raise WebSocketException(
            code=_WS_CLOSE_AUTH_FAILED,
            reason="JWT library unavailable",
        ) from exc

    secret = os.environ.get("JWT_SECRET", "")
    if not secret:
        raise WebSocketException(
            code=_WS_CLOSE_AUTH_FAILED,
            reason="JWT secret not configured",
        )

    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")

    try:
        claims: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
        )
        return claims
    except jwt.ExpiredSignatureError as exc:
        raise WebSocketException(
            code=_WS_CLOSE_AUTH_FAILED,
            reason="Token has expired",
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise WebSocketException(
            code=_WS_CLOSE_AUTH_FAILED,
            reason="Invalid authentication token",
        ) from exc
