"""Clerk JWT verification middleware and user synchronisation.

Public API
----------
``get_current_user``
    FastAPI dependency for REST endpoints — extracts the JWT from the
    ``Authorization: Bearer <token>`` header, validates it against Clerk's
    JWKS endpoint (cached in Redis for 15 minutes), syncs the user record to
    PostgreSQL, writes an audit log entry, and returns a ``UserContext``.

``ws_authenticate``
    Standalone coroutine for WebSocket connections — performs the same
    validation but accepts the JWT as a plain string (passed via the
    ``token`` query parameter during connection upgrade).

Design notes
------------
* We use PyJWT (with the ``cryptography`` extra) for RS256 verification.
* JWKS keys are cached in Redis under ``jwks:clerk`` with a 15-minute TTL
  to avoid hammering Clerk's JWKS endpoint on every request.
* On validation failure we always return HTTP 401 with the generic message
  ``"unauthenticated"`` — we never reveal *why* the token was rejected so
  that attackers cannot enumerate valid user IDs or token formats.
* PII in JWT claims (email, full name) is never written to the audit log
  to comply with the Confidential data classification in the architecture.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, NoReturn

import httpx
import jwt as pyjwt
from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import get_redis
from app.database import get_db_session
from app.models import AuditLog, User

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# 15-minute cache TTL per architecture spec.
_JWKS_CACHE_TTL_SECONDS: int = 900
_JWKS_CACHE_KEY: str = "jwks:clerk"

_http_bearer = HTTPBearer(auto_error=False)

# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _clerk_domain() -> str:
    """Return the Clerk domain from the environment (without trailing slash).

    Raises ``RuntimeError`` if ``CLERK_DOMAIN`` is not configured so the app
    fails fast at startup rather than silently issuing invalid JWKS URLs.
    """
    domain = os.environ.get("CLERK_DOMAIN", "").rstrip("/")
    if not domain:
        raise RuntimeError(
            "CLERK_DOMAIN environment variable is not set. "
            "Expected format: <slug>.clerk.accounts.dev"
        )
    return domain


def _clerk_jwks_url() -> str:
    return f"https://{_clerk_domain()}/.well-known/jwks.json"


# ---------------------------------------------------------------------------
# User context dataclass
# ---------------------------------------------------------------------------


@dataclass
class UserContext:
    """Authenticated user context injected into route handlers."""

    user_id: str  # Local PostgreSQL UUID (as string) for FK references.
    clerk_id: str  # Clerk's stable user identifier.
    display_name: str
    extra_claims: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# JWKS fetching and caching
# ---------------------------------------------------------------------------


async def fetch_jwks(redis: Any) -> dict[str, Any]:
    """Return JWKS keys, serving from Redis cache when available.

    On a cache miss the keys are fetched from Clerk's JWKS endpoint over
    HTTPS and stored in Redis with a 15-minute TTL so subsequent requests
    within that window do not incur an external HTTP call.

    Args:
        redis: An async Redis client (``redis.asyncio.Redis``).

    Returns:
        The parsed JWKS document as a dict.

    Raises:
        ``HTTPException(502)`` if Clerk's JWKS endpoint cannot be reached.
    """
    cached = await redis.get(_JWKS_CACHE_KEY)
    if cached:
        return json.loads(cached)  # type: ignore[return-value]

    jwks_url = _clerk_jwks_url()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            jwks: dict[str, Any] = response.json()
    except httpx.HTTPError as exc:
        logger.error("Failed to fetch JWKS from %s: %s", jwks_url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to reach authentication provider. Please retry.",
        ) from exc

    await redis.setex(_JWKS_CACHE_KEY, _JWKS_CACHE_TTL_SECONDS, json.dumps(jwks))
    return jwks


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


async def validate_token(token: str, redis: Any) -> dict[str, Any]:
    """Decode and validate a Clerk-issued JWT.

    Verifies:
    * Signature using the RS256 public keys from Clerk's JWKS endpoint.
    * ``iss`` claim matches the expected Clerk issuer.
    * ``exp`` claim (token has not expired).
    * ``azp`` / ``aud`` audience claim when ``CLERK_AUDIENCE`` env var is set.

    Args:
        token: Raw JWT string (without the ``Bearer `` prefix).
        redis:  Async Redis client used for JWKS caching.

    Returns:
        Decoded JWT payload as a dict.

    Raises:
        ``HTTPException(401)`` for any validation failure.
    """
    jwks = await fetch_jwks(redis)

    # Build the PyJWT JWKS client from the fetched JWKS document.
    jwks_client = pyjwt.PyJWKSet.from_dict(jwks)

    # Determine which key matches the JWT's ``kid`` header.
    try:
        header = pyjwt.get_unverified_header(token)
    except pyjwt.DecodeError:
        _raise_unauthenticated()

    kid = header.get("kid")
    signing_key = None
    for key in jwks_client.keys:
        if key.key_id == kid:
            signing_key = key
            break

    if signing_key is None:
        # No matching key — may happen if Clerk rotated keys and the TTL
        # hasn't expired yet.  Evict the cache and raise so the caller can
        # retry (or just return 401).
        await redis.delete(_JWKS_CACHE_KEY)
        _raise_unauthenticated()

    issuer = f"https://{_clerk_domain()}"
    decode_options: dict[str, Any] = {"verify_exp": True}
    audience = os.environ.get("CLERK_AUDIENCE")

    try:
        payload: dict[str, Any] = pyjwt.decode(
            token,
            key=signing_key.key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options=decode_options,
        )
    except pyjwt.ExpiredSignatureError:
        _raise_unauthenticated()
    except pyjwt.InvalidIssuerError:
        _raise_unauthenticated()
    except pyjwt.InvalidAudienceError:
        _raise_unauthenticated()
    except pyjwt.PyJWTError:
        _raise_unauthenticated()

    return payload


def _raise_unauthenticated() -> NoReturn:
    """Raise HTTP 401 with a generic, non-revealing error body."""
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": "unauthenticated"},
        headers={"WWW-Authenticate": "Bearer"},
    )


# ---------------------------------------------------------------------------
# User synchronisation
# ---------------------------------------------------------------------------


async def sync_user(
    clerk_id: str,
    display_name: str,
    db: AsyncSession,
) -> User:
    """Upsert a user record in PostgreSQL.

    On first login this creates a new row; on subsequent logins it updates
    the ``display_name`` if it has changed (Clerk allows users to rename
    themselves).  The ``locale`` column defaults to ``"en"`` and is not
    overwritten here — it is managed by the user-profile endpoint.

    Args:
        clerk_id:     Clerk's stable user identifier (``sub`` claim).
        display_name: Human-readable name extracted from JWT claims.
        db:           An active async SQLAlchemy session.

    Returns:
        The ``User`` ORM instance (either newly created or existing).
    """
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        user = User(clerk_id=clerk_id, display_name=display_name, locale="en")
        db.add(user)
    elif user.display_name != display_name:
        # Sync name changes from Clerk without clobbering other profile fields.
        user.display_name = display_name

    await db.commit()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


async def _write_audit_log(
    db: AsyncSession,
    *,
    action: str,
    actor_id: str | None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Insert an ``AuditLog`` row for auth events.

    Failures are intentionally caught and logged rather than re-raised —
    audit log writes are best-effort and must not break the auth flow.
    """
    try:
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            entity_type="user",
            entity_id=actor_id,
            metadata_=metadata,
        )
        db.add(entry)
        await db.commit()
    except Exception:
        # Never let audit log failures break authentication.
        logger.exception(
            "Failed to write audit log entry action=%s actor_id=%s", action, actor_id
        )


# ---------------------------------------------------------------------------
# FastAPI dependency — REST endpoints
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_http_bearer),
    db: AsyncSession = Depends(get_db_session),
    redis: Any = Depends(get_redis),
) -> UserContext:
    """FastAPI dependency that authenticates a REST request.

    Extracts the JWT from the ``Authorization: Bearer <token>`` header,
    validates it, syncs the user to PostgreSQL, logs the auth event, and
    returns a ``UserContext`` that route handlers can depend on.

    Example usage::

        @router.get("/api/me")
        async def me(user: UserContext = Depends(get_current_user)):
            return {"user_id": user.user_id}

    Raises:
        ``HTTPException(401)`` if the token is missing, expired, or invalid.
    """
    if credentials is None:
        await _write_audit_log(db, action="auth.failed", actor_id=None, metadata={"reason": "missing_token"})
        _raise_unauthenticated()

    token = credentials.credentials
    try:
        payload = await validate_token(token, redis)
    except HTTPException:
        # Log before re-raising; do NOT include the token in metadata (PII/secret).
        await _write_audit_log(db, action="auth.failed", actor_id=None, metadata={"reason": "invalid_token"})
        raise

    clerk_id: str = payload.get("sub", "")
    # Prefer ``name`` claim; fall back to ``username``; then use a truncated
    # clerk_id so display_name is never empty or PII-heavy in logs.
    display_name: str = (
        payload.get("name")
        or payload.get("username")
        or f"user_{clerk_id[:8]}"
    )

    user = await sync_user(clerk_id, display_name, db)
    await _write_audit_log(
        db,
        action="auth.login",
        actor_id=clerk_id,
        # Intentionally omit email/full name from audit metadata (PII).
        metadata={"user_id": str(user.id)},
    )

    return UserContext(
        user_id=str(user.id),
        clerk_id=clerk_id,
        display_name=display_name,
        extra_claims={k: v for k, v in payload.items() if k not in ("sub", "name", "email")},
    )


# ---------------------------------------------------------------------------
# WebSocket authentication
# ---------------------------------------------------------------------------


async def ws_authenticate(
    token: str,
    db: AsyncSession,
    redis: Any,
) -> UserContext:
    """Authenticate a WebSocket connection using the JWT query parameter.

    Called during connection upgrade — if authentication fails the
    WebSocket is closed with code 4001 (application-level Unauthorized)
    rather than raising an HTTP exception.

    Usage in a WebSocket route::

        @router.websocket("/ws/rooms/{room_id}")
        async def ws_handler(
            websocket: WebSocket,
            room_id: str,
            token: str = Query(...),
        ):
            db = ...   # obtain from app state
            redis = ...
            user = await ws_authenticate(token, db, redis)
            await websocket.accept()
            ...

    Args:
        token:   Raw JWT string from the ``?token=`` query parameter.
        db:      An active async SQLAlchemy session.
        redis:   Async Redis client.

    Returns:
        ``UserContext`` for the authenticated user.

    Raises:
        ``HTTPException(401)`` on validation failure — callers should convert
        this to a WebSocket close(4001).
    """
    if not token:
        await _write_audit_log(db, action="auth.failed", actor_id=None, metadata={"reason": "missing_token", "transport": "ws"})
        _raise_unauthenticated()

    try:
        payload = await validate_token(token, redis)
    except HTTPException:
        await _write_audit_log(db, action="auth.failed", actor_id=None, metadata={"reason": "invalid_token", "transport": "ws"})
        raise

    clerk_id: str = payload.get("sub", "")
    display_name: str = (
        payload.get("name")
        or payload.get("username")
        or f"user_{clerk_id[:8]}"
    )

    user = await sync_user(clerk_id, display_name, db)
    await _write_audit_log(
        db,
        action="auth.login",
        actor_id=clerk_id,
        metadata={"user_id": str(user.id), "transport": "ws"},
    )

    return UserContext(
        user_id=str(user.id),
        clerk_id=clerk_id,
        display_name=display_name,
        extra_claims={k: v for k, v in payload.items() if k not in ("sub", "name", "email")},
    )


# ---------------------------------------------------------------------------
# Convenience WebSocket dependency (query-param token extraction)
# ---------------------------------------------------------------------------


async def ws_get_token(token: str = Query(default="")) -> str:
    """FastAPI dependency that extracts the ``token`` query param for WebSocket routes."""
    return token
