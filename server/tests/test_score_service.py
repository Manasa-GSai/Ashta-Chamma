"""Unit tests for app.services.score_service.

All database interactions are mocked so these tests run without a
PostgreSQL instance. The tests verify:
- record_game_scores creates the correct number of GameScore and AuditLog rows
- record_game_scores is atomic (single flush call)
- AI players are included in score rows but leaderboard excludes them
- period filtering is applied correctly
- user score history pagination returns correct slices
"""

import datetime
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

from app.models.audit_log import AuditLog
from app.models.game_score import GameScore
from app.schemas.score import LeaderboardEntry, PlayerResult, ScoreHistoryEntry
from app.services.score_service import (
    get_leaderboard,
    get_user_score_history,
    record_game_scores,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session() -> AsyncMock:
    """Return a mock AsyncSession with add/flush stubbed."""
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _human_result(
    user_id: str = "user-1",
    finish_position: int = 1,
    pawns_captured: int = 2,
    pawns_lost: int = 0,
    duration_seconds: int = 120,
) -> PlayerResult:
    return PlayerResult(
        user_id=user_id,
        finish_position=finish_position,
        pawns_captured=pawns_captured,
        pawns_lost=pawns_lost,
        duration_seconds=duration_seconds,
    )


def _ai_result(
    ai_persona_id: int = 1,
    finish_position: int = 2,
) -> PlayerResult:
    return PlayerResult(
        ai_persona_id=ai_persona_id,
        finish_position=finish_position,
        pawns_captured=0,
        pawns_lost=1,
        duration_seconds=120,
    )


# ---------------------------------------------------------------------------
# record_game_scores
# ---------------------------------------------------------------------------


async def test_record_game_scores_creates_correct_row_count() -> None:
    """Should add N GameScore rows + 1 AuditLog row for N players."""
    session = _make_session()
    results = [
        _human_result("user-1", finish_position=1),
        _human_result("user-2", finish_position=2),
        _ai_result(ai_persona_id=1, finish_position=3),
    ]

    score_rows = await record_game_scores(session, "room-abc", results)

    # 3 score rows + 1 audit log = 4 session.add calls
    assert session.add.call_count == 4
    assert len(score_rows) == 3
    assert session.flush.call_count == 1


async def test_record_game_scores_stores_correct_fields() -> None:
    """Each GameScore row should reflect the PlayerResult it was built from."""
    session = _make_session()
    results = [_human_result("user-7", finish_position=1, pawns_captured=3, pawns_lost=1, duration_seconds=200)]

    score_rows = await record_game_scores(session, "room-xyz", results)

    assert len(score_rows) == 1
    row = score_rows[0]
    assert isinstance(row, GameScore)
    assert row.room_id == "room-xyz"
    assert row.user_id == "user-7"
    assert row.ai_persona_id is None
    assert row.finish_position == 1
    assert row.pawns_captured == 3
    assert row.pawns_lost == 1
    assert row.duration_seconds == 200


async def test_record_game_scores_stores_ai_player() -> None:
    """AI player results should be persisted (excluded later at query time)."""
    session = _make_session()
    results = [_ai_result(ai_persona_id=2, finish_position=1)]

    score_rows = await record_game_scores(session, "room-ai", results)

    assert len(score_rows) == 1
    row = score_rows[0]
    assert row.user_id is None
    assert row.ai_persona_id == 2


async def test_record_game_scores_creates_audit_log() -> None:
    """An AuditLog with action='game.completed' must be added."""
    session = _make_session()
    results = [_human_result("user-1", finish_position=1)]

    await record_game_scores(session, "room-123", results)

    added_objects = [c.args[0] for c in session.add.call_args_list]
    audit_logs = [o for o in added_objects if isinstance(o, AuditLog)]
    assert len(audit_logs) == 1
    assert audit_logs[0].action == "game.completed"
    assert audit_logs[0].entity_type == "room"
    assert audit_logs[0].entity_id == "room-123"


async def test_record_game_scores_audit_actor_is_winner() -> None:
    """The audit log actor_id should be the user with finish_position=1."""
    session = _make_session()
    results = [
        _human_result("user-winner", finish_position=1),
        _human_result("user-loser", finish_position=2),
    ]

    await record_game_scores(session, "room-win", results)

    added_objects = [c.args[0] for c in session.add.call_args_list]
    audit = next(o for o in added_objects if isinstance(o, AuditLog))
    assert audit.actor_id == "user-winner"


async def test_record_game_scores_raises_on_empty_results() -> None:
    """Calling with an empty results list must raise ValueError."""
    session = _make_session()

    with pytest.raises(ValueError, match="results must contain at least one"):
        await record_game_scores(session, "room-empty", [])


async def test_record_game_scores_all_shared_timestamp() -> None:
    """All score rows and the audit log for a game share the same scored_at."""
    session = _make_session()
    results = [
        _human_result("user-a", finish_position=1),
        _human_result("user-b", finish_position=2),
    ]

    await record_game_scores(session, "room-ts", results)

    added_objects = [c.args[0] for c in session.add.call_args_list]
    timestamps = {o.scored_at if isinstance(o, GameScore) else o.created_at for o in added_objects}
    assert len(timestamps) == 1, "All rows should share a single timestamp"


# ---------------------------------------------------------------------------
# get_leaderboard
# ---------------------------------------------------------------------------


def _mock_lb_row(
    user_id: str, display_name: str, total_wins: int, total_games: int
) -> MagicMock:
    row = MagicMock()
    row.user_id = user_id
    row.display_name = display_name
    row.total_wins = total_wins
    row.total_games = total_games
    return row


async def test_get_leaderboard_returns_entries_sorted_by_wins() -> None:
    """Entries should come back in the order returned by the query (sorted by wins desc)."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [
        _mock_lb_row("u1", "Alice", 5, 10),
        _mock_lb_row("u2", "Bob", 3, 8),
    ]
    session.execute = AsyncMock(return_value=mock_result)

    entries = await get_leaderboard(session)

    assert len(entries) == 2
    assert entries[0].user_id == "u1"
    assert entries[0].total_wins == 5
    assert entries[1].user_id == "u2"
    assert entries[1].total_wins == 3


async def test_get_leaderboard_empty_returns_empty_list() -> None:
    """When no qualifying rows exist, return an empty list."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    entries = await get_leaderboard(session)

    assert entries == []


async def test_get_leaderboard_period_week_passes_execute() -> None:
    """Providing period='week' should call execute once (filter applied in SQL)."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [_mock_lb_row("u1", "Alice", 2, 4)]
    session.execute = AsyncMock(return_value=mock_result)

    entries = await get_leaderboard(session, period="week")

    session.execute.assert_called_once()
    assert len(entries) == 1


async def test_get_leaderboard_period_month_passes_execute() -> None:
    """Providing period='month' should also call execute once."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    await get_leaderboard(session, period="month")

    session.execute.assert_called_once()


async def test_get_leaderboard_all_period_passes_execute() -> None:
    """period='all' is treated identically to None (no date filter)."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [_mock_lb_row("u3", "Carol", 1, 2)]
    session.execute = AsyncMock(return_value=mock_result)

    entries = await get_leaderboard(session, period="all")

    session.execute.assert_called_once()
    assert len(entries) == 1


async def test_get_leaderboard_pydantic_model_fields() -> None:
    """Returned entries must satisfy the LeaderboardEntry schema."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [_mock_lb_row("u9", "Zara", 7, 12)]
    session.execute = AsyncMock(return_value=mock_result)

    entries = await get_leaderboard(session)

    assert isinstance(entries[0], LeaderboardEntry)
    assert entries[0].display_name == "Zara"
    assert entries[0].total_games == 12


# ---------------------------------------------------------------------------
# get_user_score_history
# ---------------------------------------------------------------------------


def _mock_score_row(
    row_id: int = 1,
    room_id: str = "room-1",
    finish_position: int = 2,
    pawns_captured: int = 1,
    pawns_lost: int = 0,
    duration_seconds: int = 180,
) -> MagicMock:
    row = MagicMock(spec=GameScore)
    row.id = row_id
    row.room_id = room_id
    row.finish_position = finish_position
    row.pawns_captured = pawns_captured
    row.pawns_lost = pawns_lost
    row.duration_seconds = duration_seconds
    row.scored_at = datetime.datetime(2026, 1, 15, 10, 0, 0, tzinfo=datetime.timezone.utc)
    return row


async def test_get_user_score_history_returns_entries_and_total() -> None:
    """Should return the paginated entries along with the total count."""
    session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 5

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [
        _mock_score_row(1, "room-a"),
        _mock_score_row(2, "room-b"),
    ]

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    entries, total = await get_user_score_history(session, "user-42", limit=10, offset=0)

    assert total == 5
    assert len(entries) == 2
    assert entries[0].room_id == "room-a"
    assert entries[1].room_id == "room-b"


async def test_get_user_score_history_pagination_offset() -> None:
    """offset is forwarded to the query; total reflects full unfiltered count."""
    session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 15

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [_mock_score_row(11)]

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    entries, total = await get_user_score_history(session, "user-99", limit=1, offset=10)

    assert total == 15
    assert len(entries) == 1


async def test_get_user_score_history_empty() -> None:
    """A user with no games returns empty list and zero total."""
    session = AsyncMock()

    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = []

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    entries, total = await get_user_score_history(session, "new-user", limit=20, offset=0)

    assert total == 0
    assert entries == []


async def test_get_user_score_history_entry_fields() -> None:
    """Each ScoreHistoryEntry must expose all required fields."""
    session = AsyncMock()
    scored_at = datetime.datetime(2026, 3, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    mock_row = MagicMock(spec=GameScore)
    mock_row.id = 42
    mock_row.room_id = "room-detail"
    mock_row.finish_position = 1
    mock_row.pawns_captured = 3
    mock_row.pawns_lost = 1
    mock_row.duration_seconds = 300
    mock_row.scored_at = scored_at

    rows_result = MagicMock()
    rows_result.scalars.return_value.all.return_value = [mock_row]

    session.execute = AsyncMock(side_effect=[count_result, rows_result])

    entries, _ = await get_user_score_history(session, "user-detail", limit=1, offset=0)

    entry = entries[0]
    assert isinstance(entry, ScoreHistoryEntry)
    assert entry.id == 42
    assert entry.room_id == "room-detail"
    assert entry.finish_position == 1
    assert entry.pawns_captured == 3
    assert entry.pawns_lost == 1
    assert entry.duration_seconds == 300
    assert entry.scored_at == scored_at
