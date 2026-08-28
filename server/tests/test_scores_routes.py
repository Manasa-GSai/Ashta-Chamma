"""Integration tests for score-related REST endpoints.

Uses FastAPI's TestClient with dependency overrides to:
- Bypass JWT auth (inject a fixed user_id)
- Bypass the database (inject a no-op async session)
- Patch score_service functions to return controlled data

This approach tests the route layer in isolation: HTTP contract,
response shape, status codes, and parameter validation.
"""

import datetime
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.dependencies import get_current_user_id
from app.main import app
from app.schemas.score import LeaderboardEntry, ScoreHistoryEntry, ScoreHistoryResponse

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TEST_USER_ID = "test-user-uuid"


async def _override_get_db() -> AsyncGenerator[AsyncMock, None]:
    """Yield a no-op mock session to satisfy Depends(get_db)."""
    yield AsyncMock()


@pytest.fixture()
def client() -> TestClient:
    """TestClient with auth and DB dependencies overridden."""
    app.dependency_overrides[get_current_user_id] = lambda: _TEST_USER_ID
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def unauthed_client() -> TestClient:
    """TestClient with only the DB dependency overridden (no auth bypass)."""
    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _lb_entry(
    user_id: str = "u1",
    display_name: str = "Alice",
    total_wins: int = 5,
    total_games: int = 10,
) -> LeaderboardEntry:
    return LeaderboardEntry(
        user_id=user_id,
        display_name=display_name,
        total_wins=total_wins,
        total_games=total_games,
    )


def _score_entry(
    entry_id: int = 1,
    room_id: str = "room-1",
    finish_position: int = 2,
) -> ScoreHistoryEntry:
    return ScoreHistoryEntry(
        id=entry_id,
        room_id=room_id,
        finish_position=finish_position,
        pawns_captured=1,
        pawns_lost=0,
        duration_seconds=180,
        scored_at=datetime.datetime(2026, 1, 10, 8, 0, 0, tzinfo=datetime.timezone.utc),
    )


# ---------------------------------------------------------------------------
# GET /api/scores/leaderboard
# ---------------------------------------------------------------------------


def test_leaderboard_returns_200_with_entries(client: TestClient) -> None:
    entries = [_lb_entry("u1", "Alice", 5, 10), _lb_entry("u2", "Bob", 3, 7)]
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=entries,
    ):
        resp = client.get("/api/scores/leaderboard")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["user_id"] == "u1"
    assert data[0]["total_wins"] == 5
    assert data[1]["user_id"] == "u2"


def test_leaderboard_empty_returns_empty_array(client: TestClient) -> None:
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = client.get("/api/scores/leaderboard")

    assert resp.status_code == 200
    assert resp.json() == []


def test_leaderboard_period_week_accepted(client: TestClient) -> None:
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=[_lb_entry()],
    ) as mock_lb:
        resp = client.get("/api/scores/leaderboard?period=week")

    assert resp.status_code == 200
    # Verify the service was called with period='week'
    mock_lb.assert_called_once()
    call_kwargs = mock_lb.call_args
    assert call_kwargs.kwargs.get("period") == "week" or (
        len(call_kwargs.args) > 1 and call_kwargs.args[1] == "week"
    )


def test_leaderboard_period_month_accepted(client: TestClient) -> None:
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = client.get("/api/scores/leaderboard?period=month")

    assert resp.status_code == 200


def test_leaderboard_period_all_accepted(client: TestClient) -> None:
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = client.get("/api/scores/leaderboard?period=all")

    assert resp.status_code == 200


def test_leaderboard_invalid_period_returns_400(client: TestClient) -> None:
    resp = client.get("/api/scores/leaderboard?period=year")

    assert resp.status_code == 400
    assert "period" in resp.json()["detail"].lower()


def test_leaderboard_response_schema(client: TestClient) -> None:
    """Each entry must have the required LeaderboardEntry fields."""
    entries = [_lb_entry("u5", "Eve", 8, 15)]
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=entries,
    ):
        resp = client.get("/api/scores/leaderboard")

    data = resp.json()
    entry = data[0]
    assert set(entry.keys()) >= {"user_id", "display_name", "total_wins", "total_games"}


def test_leaderboard_accessible_without_auth(unauthed_client: TestClient) -> None:
    """Leaderboard is public — no auth required."""
    with patch(
        "app.routes.scores.get_leaderboard",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = unauthed_client.get("/api/scores/leaderboard")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# GET /api/users/me/scores
# ---------------------------------------------------------------------------


def test_my_scores_returns_200_with_entries(client: TestClient) -> None:
    history = ScoreHistoryResponse(
        entries=[_score_entry(1, "room-a"), _score_entry(2, "room-b")],
        total=2,
        limit=20,
        offset=0,
    )
    with patch(
        "app.routes.scores.get_user_score_history",
        new_callable=AsyncMock,
        return_value=(history.entries, history.total),
    ):
        resp = client.get("/api/users/me/scores")

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["entries"]) == 2
    assert data["entries"][0]["room_id"] == "room-a"


def test_my_scores_includes_pagination_metadata(client: TestClient) -> None:
    with patch(
        "app.routes.scores.get_user_score_history",
        new_callable=AsyncMock,
        return_value=([], 50),
    ):
        resp = client.get("/api/users/me/scores?limit=5&offset=10")

    data = resp.json()
    assert data["total"] == 50
    assert data["limit"] == 5
    assert data["offset"] == 10


def test_my_scores_default_pagination(client: TestClient) -> None:
    with patch(
        "app.routes.scores.get_user_score_history",
        new_callable=AsyncMock,
        return_value=([], 0),
    ):
        resp = client.get("/api/users/me/scores")

    assert resp.status_code == 200
    data = resp.json()
    assert data["limit"] == 20
    assert data["offset"] == 0


def test_my_scores_requires_auth(unauthed_client: TestClient) -> None:
    """Without auth header, /api/users/me/scores returns 403."""
    resp = unauthed_client.get("/api/users/me/scores")

    assert resp.status_code in (401, 403)


def test_my_scores_invalid_limit_returns_422(client: TestClient) -> None:
    """limit=0 violates ge=1 constraint — FastAPI returns 422."""
    resp = client.get("/api/users/me/scores?limit=0")

    assert resp.status_code == 422


def test_my_scores_limit_exceeds_max_returns_422(client: TestClient) -> None:
    """limit>100 violates le=100 constraint."""
    resp = client.get("/api/users/me/scores?limit=101")

    assert resp.status_code == 422


def test_my_scores_entry_schema(client: TestClient) -> None:
    """Each ScoreHistoryEntry must have the required fields."""
    entry = _score_entry(99, "room-schema", finish_position=1)
    with patch(
        "app.routes.scores.get_user_score_history",
        new_callable=AsyncMock,
        return_value=([entry], 1),
    ):
        resp = client.get("/api/users/me/scores")

    data = resp.json()
    record = data["entries"][0]
    assert set(record.keys()) >= {
        "id", "room_id", "finish_position", "pawns_captured", "pawns_lost",
        "duration_seconds", "scored_at",
    }
    assert record["id"] == 99
    assert record["finish_position"] == 1


def test_my_scores_only_returns_current_user_data(client: TestClient) -> None:
    """The service must be called with the current user's id, not another's."""
    with patch(
        "app.routes.scores.get_user_score_history",
        new_callable=AsyncMock,
        return_value=([], 0),
    ) as mock_hist:
        client.get("/api/users/me/scores")

    mock_hist.assert_called_once()
    # Second positional arg after session is user_id
    call_kwargs = mock_hist.call_args
    assert _TEST_USER_ID in call_kwargs.args or call_kwargs.kwargs.get("user_id") == _TEST_USER_ID


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_endpoint(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
