"""Tests for SecurityHeadersMiddleware.

Verifies that all OWASP-required security headers are present on every HTTP
response, regardless of which route handled the request.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware.security_headers import SecurityHeadersMiddleware, _SECURITY_HEADERS


def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with the security headers middleware."""
    test_app = FastAPI()
    test_app.add_middleware(SecurityHeadersMiddleware)

    @test_app.get("/test")
    async def _test_route() -> dict[str, str]:
        return {"ok": "true"}

    @test_app.get("/api/health")
    async def _health() -> dict[str, str]:
        return {"status": "ok"}

    return test_app


_app = _make_app()
_client = TestClient(_app)


def test_x_content_type_options_present() -> None:
    response = _client.get("/test")
    assert response.headers.get("x-content-type-options") == "nosniff"


def test_x_frame_options_present() -> None:
    response = _client.get("/test")
    assert response.headers.get("x-frame-options") == "DENY"


def test_hsts_header_present_with_one_year_max_age() -> None:
    response = _client.get("/test")
    hsts = response.headers.get("strict-transport-security", "")
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


def test_all_required_headers_present_on_health_endpoint() -> None:
    response = _client.get("/api/health")
    for header in ("x-content-type-options", "x-frame-options", "strict-transport-security"):
        assert header in response.headers, f"Missing header: {header}"


def test_security_headers_on_404_response() -> None:
    response = _client.get("/nonexistent", follow_redirects=False)
    assert response.headers.get("x-content-type-options") == "nosniff"
    assert response.headers.get("x-frame-options") == "DENY"
    hsts = response.headers.get("strict-transport-security", "")
    assert "max-age=31536000" in hsts


def test_all_configured_headers_applied() -> None:
    """Every header in the middleware constant is present on a normal response."""
    response = _client.get("/test")
    for header_name in _SECURITY_HEADERS:
        assert header_name.lower() in response.headers, f"Header missing: {header_name}"
