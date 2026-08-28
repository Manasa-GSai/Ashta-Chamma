"""Tests for the FastAPI application entry point (app/main.py).

Covers:
- Application creation and correct metadata.
- OpenAPI documentation endpoints (/docs, /redoc, /openapi.json).
- Health check endpoint happy path and response shape.
"""

import pytest
from fastapi.testclient import TestClient

from app import __version__
from app.main import app, create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> TestClient:
    """Return a synchronous test client for the FastAPI app."""
    return TestClient(app)


# ---------------------------------------------------------------------------
# Application creation
# ---------------------------------------------------------------------------


def test_create_app_returns_fastapi_instance() -> None:
    """create_app() returns a new FastAPI instance each time."""
    from fastapi import FastAPI

    result = create_app()
    assert isinstance(result, FastAPI)


def test_app_title() -> None:
    """Application title is set correctly for OpenAPI metadata."""
    assert app.title == "Ashta Chamma 3D"


def test_app_version_matches_package_version() -> None:
    """Application version matches the package __version__ constant."""
    assert app.version == __version__


def test_app_has_openapi_tags() -> None:
    """Application exposes expected tag names for route grouping."""
    tag_names = {tag["name"] for tag in (app.openapi_tags or [])}
    expected = {"health", "rooms", "users", "scores", "websocket"}
    assert expected.issubset(tag_names)


# ---------------------------------------------------------------------------
# OpenAPI documentation endpoints
# ---------------------------------------------------------------------------


def test_openapi_json_accessible(client: TestClient) -> None:
    """GET /openapi.json returns 200 with a valid OpenAPI schema."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Ashta Chamma 3D"
    assert "paths" in data


def test_swagger_ui_accessible(client: TestClient) -> None:
    """GET /docs returns 200 (Swagger UI)."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_redoc_accessible(client: TestClient) -> None:
    """GET /redoc returns 200 (ReDoc UI)."""
    response = client.get("/redoc")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Health check endpoint
# ---------------------------------------------------------------------------


def test_health_check_returns_200(client: TestClient) -> None:
    """GET /api/health returns HTTP 200."""
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_check_response_shape(client: TestClient) -> None:
    """GET /api/health returns the expected JSON payload shape."""
    response = client.get("/api/health")
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_health_check_status_is_ok(client: TestClient) -> None:
    """GET /api/health returns status == 'ok'."""
    response = client.get("/api/health")
    assert response.json()["status"] == "ok"


def test_health_check_version_matches(client: TestClient) -> None:
    """GET /api/health returns version matching __version__."""
    response = client.get("/api/health")
    assert response.json()["version"] == __version__


def test_health_check_content_type_is_json(client: TestClient) -> None:
    """GET /api/health returns application/json content type."""
    response = client.get("/api/health")
    assert "application/json" in response.headers["content-type"]


def test_health_check_requires_no_auth(client: TestClient) -> None:
    """GET /api/health succeeds without an Authorization header."""
    response = client.get("/api/health", headers={})
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Health check is discoverable in OpenAPI schema
# ---------------------------------------------------------------------------


def test_health_check_in_openapi_schema(client: TestClient) -> None:
    """The /api/health path is included in the generated OpenAPI schema."""
    schema = client.get("/openapi.json").json()
    assert "/api/health" in schema["paths"]


def test_health_check_tagged_correctly(client: TestClient) -> None:
    """The /api/health endpoint is tagged with 'health' in OpenAPI schema."""
    schema = client.get("/openapi.json").json()
    health_path = schema["paths"].get("/api/health", {})
    get_op = health_path.get("get", {})
    assert "health" in get_op.get("tags", [])
