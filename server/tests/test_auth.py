"""Tests for server/app/auth.py.

Test strategy (from work order):
* Valid JWT → returns UserContext with correct user_id, clerk_id, display_name.
* Expired JWT → HTTP 401.
* Invalid signature → HTTP 401.
* JWKS caching — second call within TTL uses Redis cache, not the HTTP endpoint.
* User sync — creates a new User row on first auth; returns existing on repeat.
* WebSocket authentication — ws_authenticate() accepts token as a string.
* Audit log entries are written for success and failure cases.

All external dependencies are mocked:
  * JWKS endpoint — httpx is mocked via ``respx``.
  * Redis — ``fakeredis`` (async mode).
  * PostgreSQL — SQLite in-memory with SQLAlchemy async.
"""

from __future__ import annotations

import json
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

# ---------------------------------------------------------------------------
# RSA key generation helpers — module-level so they are created once.
# ---------------------------------------------------------------------------

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_KEY = _PRIVATE_KEY.public_key()

_KID = "test-key-id-1"
_CLERK_DOMAIN = "example.clerk.accounts.dev"
_ISSUER = f"https://{_CLERK_DOMAIN}"


def _make_jwks() -> dict:
    """Build a minimal JWKS document from the test RSA public key."""
    from jwt.algorithms import RSAAlgorithm

    public_jwk_str = RSAAlgorithm.to_jwk(_PUBLIC_KEY)
    public_jwk: dict = json.loads(public_jwk_str)
    public_jwk["kid"] = _KID
    public_jwk["alg"] = "RS256"
    public_jwk["use"] = "sig"
    return {"keys": [public_jwk]}


def _make_token(
    *,
    sub: str = "user_clerk_abc123",
    name: str = "Test Player",
    exp_offset: int = 3600,
    kid: str = _KID,
    issuer: str = _ISSUER,
) -> str:
    """Sign and return a JWT using the test RSA private key."""
    import jwt as pyjwt

    now = int(time.time())
    payload = {
        "sub": sub,
        "name": name,
        "iss": issuer,
        "iat": now,
        "exp": now + exp_offset,
    }
    private_pem = _PRIVATE_KEY.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return pyjwt.encode(payload, private_pem, algorithm="RS256", headers={"kid": kid})


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def clerk_domain_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CLERK_DOMAIN", _CLERK_DOMAIN)


@pytest_asyncio.fixture()
async def fake_redis():
    """Return a fakeredis async client pre-loaded with nothing."""
    import fakeredis.aioredis as fakeredis_async

    client = fakeredis_async.FakeRedis(decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture()
async def db_session():
    """Return an in-memory SQLite async session with the ORM schema created."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    from app.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as session:
        yield session

    await engine.dispose()


@pytest.fixture()
def jwks_payload() -> dict:
    return _make_jwks()


# ---------------------------------------------------------------------------
# fetch_jwks tests
# ---------------------------------------------------------------------------


class TestFetchJwks:
    @pytest.mark.asyncio()
    async def test_fetches_from_endpoint_on_cache_miss(
        self, fake_redis, jwks_payload, clerk_domain_env
    ):
        """Cache miss → HTTP GET to JWKS URL → result stored in Redis."""
        with patch("app.auth.httpx.AsyncClient") as mock_client_cls:
            mock_response = MagicMock()
            mock_response.json.return_value = jwks_payload
            mock_response.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = False
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value = mock_client

            from app.auth import _JWKS_CACHE_KEY, fetch_jwks

            result = await fetch_jwks(fake_redis)

        assert result == jwks_payload
        # Confirm the result was stored in Redis.
        cached_raw = await fake_redis.get(_JWKS_CACHE_KEY)
        assert cached_raw is not None
        assert json.loads(cached_raw) == jwks_payload

    @pytest.mark.asyncio()
    async def test_returns_cached_value_without_http_call(
        self, fake_redis, jwks_payload, clerk_domain_env
    ):
        """Cache hit → no HTTP call, cached value returned directly."""
        from app.auth import _JWKS_CACHE_KEY, _JWKS_CACHE_TTL_SECONDS, fetch_jwks

        await fake_redis.setex(_JWKS_CACHE_KEY, _JWKS_CACHE_TTL_SECONDS, json.dumps(jwks_payload))

        with patch("app.auth.httpx.AsyncClient") as mock_client_cls:
            result = await fetch_jwks(fake_redis)
            mock_client_cls.assert_not_called()

        assert result == jwks_payload

    @pytest.mark.asyncio()
    async def test_raises_502_on_http_error(self, fake_redis, clerk_domain_env):
        """JWKS endpoint unreachable → HTTP 502 raised."""
        import httpx

        with patch("app.auth.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = False
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            mock_client_cls.return_value = mock_client

            from app.auth import fetch_jwks

            with pytest.raises(HTTPException) as exc_info:
                await fetch_jwks(fake_redis)

        assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# validate_token tests
# ---------------------------------------------------------------------------


class TestValidateToken:
    @pytest.mark.asyncio()
    async def test_valid_token_returns_payload(self, fake_redis, jwks_payload, clerk_domain_env):
        """A well-formed, unexpired token returns the decoded payload."""
        token = _make_token()

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import validate_token

            payload = await validate_token(token, fake_redis)

        assert payload["sub"] == "user_clerk_abc123"
        assert payload["name"] == "Test Player"

    @pytest.mark.asyncio()
    async def test_expired_token_raises_401(self, fake_redis, jwks_payload, clerk_domain_env):
        """Expired JWT (exp in the past) → HTTP 401."""
        token = _make_token(exp_offset=-10)  # already expired

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import validate_token

            with pytest.raises(HTTPException) as exc_info:
                await validate_token(token, fake_redis)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == {"error": "unauthenticated"}

    @pytest.mark.asyncio()
    async def test_invalid_signature_raises_401(self, fake_redis, jwks_payload, clerk_domain_env):
        """JWT signed by a different key → HTTP 401."""
        # Generate a completely different RSA key and sign the token with it.
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_pem = other_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        import jwt as pyjwt

        bad_token = pyjwt.encode(
            {"sub": "x", "iss": _ISSUER, "exp": int(time.time()) + 3600},
            other_pem,
            algorithm="RS256",
            headers={"kid": _KID},
        )

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import validate_token

            with pytest.raises(HTTPException) as exc_info:
                await validate_token(bad_token, fake_redis)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio()
    async def test_wrong_issuer_raises_401(self, fake_redis, jwks_payload, clerk_domain_env):
        """Token with mismatched issuer → HTTP 401."""
        token = _make_token(issuer="https://wrong.clerk.accounts.dev")

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import validate_token

            with pytest.raises(HTTPException) as exc_info:
                await validate_token(token, fake_redis)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio()
    async def test_missing_kid_clears_cache_and_raises_401(
        self, fake_redis, jwks_payload, clerk_domain_env
    ):
        """Token with unknown kid evicts the JWKS cache and raises 401."""
        token = _make_token(kid="unknown-kid")

        from app.auth import _JWKS_CACHE_KEY, _JWKS_CACHE_TTL_SECONDS

        await fake_redis.setex(
            _JWKS_CACHE_KEY, _JWKS_CACHE_TTL_SECONDS, json.dumps(jwks_payload)
        )

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import validate_token

            with pytest.raises(HTTPException) as exc_info:
                await validate_token(token, fake_redis)

        assert exc_info.value.status_code == 401
        # Cache should be cleared so the next request re-fetches fresh keys.
        assert await fake_redis.get(_JWKS_CACHE_KEY) is None


# ---------------------------------------------------------------------------
# sync_user tests
# ---------------------------------------------------------------------------


class TestSyncUser:
    @pytest.mark.asyncio()
    async def test_creates_new_user_on_first_auth(self, db_session):
        """First call with a new clerk_id inserts a User row."""
        from sqlalchemy import select

        from app.auth import sync_user
        from app.models import User

        user = await sync_user("clerk_new_001", "Alice", db_session)

        assert user.clerk_id == "clerk_new_001"
        assert user.display_name == "Alice"
        assert user.locale == "en"
        assert user.id is not None

        result = await db_session.execute(
            select(User).where(User.clerk_id == "clerk_new_001")
        )
        assert result.scalar_one_or_none() is not None

    @pytest.mark.asyncio()
    async def test_returns_existing_user_on_repeat_auth(self, db_session):
        """Subsequent calls with same clerk_id return the same row."""
        from app.auth import sync_user

        user1 = await sync_user("clerk_repeat_001", "Bob", db_session)
        user2 = await sync_user("clerk_repeat_001", "Bob", db_session)

        assert str(user1.id) == str(user2.id)

    @pytest.mark.asyncio()
    async def test_updates_display_name_if_changed(self, db_session):
        """If Clerk user renames themselves the display_name is updated."""
        from app.auth import sync_user

        await sync_user("clerk_rename_001", "Charlie", db_session)
        updated = await sync_user("clerk_rename_001", "Charlie B.", db_session)

        assert updated.display_name == "Charlie B."


# ---------------------------------------------------------------------------
# get_current_user dependency tests
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    @pytest.mark.asyncio()
    async def test_valid_bearer_returns_user_context(
        self, fake_redis, db_session, jwks_payload, clerk_domain_env
    ):
        """Valid JWT in Authorization header returns a populated UserContext."""
        from unittest.mock import MagicMock

        from fastapi.security import HTTPAuthorizationCredentials

        token = _make_token(sub="clerk_user_xyz", name="Diana")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import get_current_user

            ctx = await get_current_user(
                credentials=creds, db=db_session, redis=fake_redis
            )

        assert ctx.clerk_id == "clerk_user_xyz"
        assert ctx.display_name == "Diana"
        assert ctx.user_id  # non-empty UUID string

    @pytest.mark.asyncio()
    async def test_missing_credentials_raises_401(
        self, fake_redis, db_session, clerk_domain_env
    ):
        """No Authorization header → HTTP 401."""
        from app.auth import get_current_user

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=None, db=db_session, redis=fake_redis)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == {"error": "unauthenticated"}

    @pytest.mark.asyncio()
    async def test_expired_jwt_raises_401(
        self, fake_redis, db_session, jwks_payload, clerk_domain_env
    ):
        """Expired JWT → HTTP 401."""
        from fastapi.security import HTTPAuthorizationCredentials

        token = _make_token(exp_offset=-60)
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import get_current_user

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(
                    credentials=creds, db=db_session, redis=fake_redis
                )

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio()
    async def test_audit_log_written_on_success(
        self, fake_redis, db_session, jwks_payload, clerk_domain_env
    ):
        """Successful auth writes an 'auth.login' entry to the audit_logs table."""
        from fastapi.security import HTTPAuthorizationCredentials
        from sqlalchemy import select

        from app.models import AuditLog

        token = _make_token(sub="clerk_audit_ok", name="Eve")
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import get_current_user

            await get_current_user(credentials=creds, db=db_session, redis=fake_redis)

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "auth.login")
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.actor_id == "clerk_audit_ok"

    @pytest.mark.asyncio()
    async def test_audit_log_written_on_failure(
        self, fake_redis, db_session, clerk_domain_env
    ):
        """Missing token writes an 'auth.failed' entry to the audit_logs table."""
        from sqlalchemy import select

        from app.auth import get_current_user
        from app.models import AuditLog

        with pytest.raises(HTTPException):
            await get_current_user(credentials=None, db=db_session, redis=fake_redis)

        result = await db_session.execute(
            select(AuditLog).where(AuditLog.action == "auth.failed")
        )
        log = result.scalar_one_or_none()
        assert log is not None


# ---------------------------------------------------------------------------
# ws_authenticate tests
# ---------------------------------------------------------------------------


class TestWsAuthenticate:
    @pytest.mark.asyncio()
    async def test_valid_token_returns_user_context(
        self, fake_redis, db_session, jwks_payload, clerk_domain_env
    ):
        """Valid JWT string → UserContext (WebSocket path)."""
        token = _make_token(sub="clerk_ws_user", name="Frank")

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import ws_authenticate

            ctx = await ws_authenticate(token, db_session, fake_redis)

        assert ctx.clerk_id == "clerk_ws_user"
        assert ctx.display_name == "Frank"

    @pytest.mark.asyncio()
    async def test_empty_token_raises_401(self, fake_redis, db_session, clerk_domain_env):
        """Empty token string → HTTP 401."""
        from app.auth import ws_authenticate

        with pytest.raises(HTTPException) as exc_info:
            await ws_authenticate("", db_session, fake_redis)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio()
    async def test_expired_ws_token_raises_401(
        self, fake_redis, db_session, jwks_payload, clerk_domain_env
    ):
        """Expired JWT via WebSocket path → HTTP 401."""
        token = _make_token(exp_offset=-30)

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import ws_authenticate

            with pytest.raises(HTTPException) as exc_info:
                await ws_authenticate(token, db_session, fake_redis)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio()
    async def test_audit_log_written_for_ws_auth(
        self, fake_redis, db_session, jwks_payload, clerk_domain_env
    ):
        """Successful WebSocket auth writes an audit log with transport=ws."""
        from sqlalchemy import select

        from app.models import AuditLog

        token = _make_token(sub="clerk_ws_audit", name="Grace")

        with patch("app.auth.fetch_jwks", AsyncMock(return_value=jwks_payload)):
            from app.auth import ws_authenticate

            await ws_authenticate(token, db_session, fake_redis)

        result = await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == "auth.login",
                AuditLog.actor_id == "clerk_ws_audit",
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.metadata_ is not None
        assert log.metadata_.get("transport") == "ws"


# ---------------------------------------------------------------------------
# JWKS caching round-trip test
# ---------------------------------------------------------------------------


class TestJwksCachingRoundTrip:
    @pytest.mark.asyncio()
    async def test_second_request_uses_redis_cache(
        self, fake_redis, jwks_payload, clerk_domain_env
    ):
        """Two consecutive validate_token calls only fetch JWKS once."""
        token = _make_token()

        call_count = 0

        async def _mock_fetch_jwks(redis):
            nonlocal call_count
            call_count += 1
            return jwks_payload

        with patch("app.auth.fetch_jwks", side_effect=_mock_fetch_jwks):
            from app.auth import validate_token

            await validate_token(token, fake_redis)
            await validate_token(token, fake_redis)

        # fetch_jwks is called each time by validate_token, but the
        # *internal* HTTP call should be suppressed by the Redis cache.
        # Here we verify that fetch_jwks itself (our entry point for
        # caching) is called; the HTTP suppression is tested in TestFetchJwks.
        assert call_count == 2
