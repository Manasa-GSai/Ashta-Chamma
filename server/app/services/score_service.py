"""Score service — persists game outcomes and queries player statistics.

Integration point with the game state machine
----------------------------------------------
When the GameStateMachine transitions to GAME_OVER it should call::

    async with session.begin():
        await score_service.record_game_scores(session, room_id, results)

``record_game_scores`` flushes all rows within the **caller's** transaction
boundary. If any row insert fails, the caller's ``session.begin()`` context
manager rolls back the entire transaction automatically, satisfying the
atomicity requirement.

All public functions accept an ``AsyncSession`` provided by the caller so
that they can be composed into larger transactions if needed and are
straightforward to unit-test via dependency injection.
"""

import datetime
import logging
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.game_score import GameScore
from app.models.user import User
from app.schemas.score import LeaderboardEntry, PlayerResult, ScoreHistoryEntry

logger = logging.getLogger(__name__)

# Supported named periods and their day counts.
Period = Literal["week", "month", "all"]
_PERIOD_DAYS: dict[str, int] = {"week": 7, "month": 30}


async def record_game_scores(
    session: AsyncSession,
    room_id: str,
    results: list[PlayerResult],
) -> list[GameScore]:
    """Persist each player's game outcome and write one audit log entry.

    All inserts share the caller-owned transaction; the caller must
    ``commit`` or ``rollback`` after this returns. ``flush`` is called
    here so that the new rows are visible within the same transaction if
    needed by subsequent operations.

    Args:
        session: Active async SQLAlchemy session.
        room_id: UUID string of the completed room.
        results: Per-player outcome data (human and AI).

    Returns:
        The newly created ``GameScore`` ORM instances (IDs assigned after
        flush).
    """
    if not results:
        raise ValueError("results must contain at least one PlayerResult")

    now = datetime.datetime.now(tz=datetime.timezone.utc)

    score_rows: list[GameScore] = []
    for result in results:
        row = GameScore(
            room_id=room_id,
            user_id=result.user_id,
            ai_persona_id=result.ai_persona_id,
            finish_position=result.finish_position,
            pawns_captured=result.pawns_captured,
            pawns_lost=result.pawns_lost,
            duration_seconds=result.duration_seconds,
            scored_at=now,
        )
        session.add(row)
        score_rows.append(row)

    # Determine the winner (lowest finish_position) for the audit actor.
    winner = min(results, key=lambda r: r.finish_position)
    audit = AuditLog(
        actor_id=winner.user_id,
        action="game.completed",
        entity_type="room",
        entity_id=room_id,
        metadata_={"room_id": room_id, "player_count": len(results)},
        created_at=now,
    )
    session.add(audit)

    await session.flush()
    logger.info("Recorded %d score rows for room %s", len(score_rows), room_id)
    return score_rows


async def get_leaderboard(
    session: AsyncSession,
    period: Period | None = None,
    limit: int = 50,
) -> list[LeaderboardEntry]:
    """Return human players ranked by total wins.

    Excludes AI players by requiring ``user_id IS NOT NULL`` and
    ``ai_persona_id IS NULL``.

    Args:
        session: Active async SQLAlchemy session.
        period: ``"week"`` (last 7 days), ``"month"`` (last 30 days), or
            ``None`` / ``"all"`` for all-time stats.
        limit: Maximum number of entries (default 50).

    Returns:
        Leaderboard entries sorted by ``total_wins`` descending.
    """
    # Count wins using a conditional sum — avoids FILTER clause for
    # compatibility, although PostgreSQL supports it natively.
    wins_expr = func.sum(
        case((GameScore.finish_position == 1, 1), else_=0)
    ).label("total_wins")
    games_expr = func.count(GameScore.id).label("total_games")

    stmt = (
        select(
            GameScore.user_id,
            User.display_name,
            wins_expr,
            games_expr,
        )
        .join(User, User.id == GameScore.user_id)
        .where(
            GameScore.user_id.is_not(None),
            GameScore.ai_persona_id.is_(None),
        )
        .group_by(GameScore.user_id, User.display_name)
        .order_by(wins_expr.desc())
        .limit(limit)
    )

    # Apply optional time-window filter before execution.
    if period and period in _PERIOD_DAYS:
        cutoff = datetime.datetime.now(tz=datetime.timezone.utc) - datetime.timedelta(
            days=_PERIOD_DAYS[period]
        )
        stmt = stmt.where(GameScore.scored_at >= cutoff)

    rows = (await session.execute(stmt)).all()
    return [
        LeaderboardEntry(
            user_id=row.user_id,
            display_name=row.display_name,
            total_wins=row.total_wins,
            total_games=row.total_games,
        )
        for row in rows
    ]


async def get_user_score_history(
    session: AsyncSession,
    user_id: str,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ScoreHistoryEntry], int]:
    """Return a user's personal game history with pagination.

    Args:
        session: Active async SQLAlchemy session.
        user_id: UUID string of the requesting user.
        limit: Page size (number of records to return).
        offset: Number of records to skip for pagination.

    Returns:
        Tuple of ``(entries, total_count)`` where ``total_count`` is the
        full unpaginated row count for the user.
    """
    base_filter = GameScore.user_id == user_id

    # Separate count query avoids fetching all rows just to count them.
    count_stmt = select(func.count()).select_from(GameScore).where(base_filter)
    total: int = (await session.execute(count_stmt)).scalar_one()

    page_stmt = (
        select(GameScore)
        .where(base_filter)
        .order_by(GameScore.scored_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await session.execute(page_stmt)).scalars().all()

    entries = [
        ScoreHistoryEntry(
            id=row.id,
            room_id=row.room_id,
            finish_position=row.finish_position,
            pawns_captured=row.pawns_captured,
            pawns_lost=row.pawns_lost,
            duration_seconds=row.duration_seconds,
            scored_at=row.scored_at,
        )
        for row in rows
    ]
    return entries, total
