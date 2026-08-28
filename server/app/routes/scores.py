"""Score and leaderboard REST endpoints.

Exposes two routers that are registered in ``app.main``:

- ``leaderboard_router``  →  prefix ``/api/scores``
    GET /api/scores/leaderboard

- ``user_scores_router``  →  prefix ``/api/users``
    GET /api/users/me/scores
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.schemas.score import LeaderboardEntry, ScoreHistoryResponse
from app.services.score_service import (
    Period,
    get_leaderboard,
    get_user_score_history,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Leaderboard router — public (no auth required)
# ---------------------------------------------------------------------------

leaderboard_router = APIRouter(prefix="/api/scores", tags=["scores"])


@leaderboard_router.get(
    "/leaderboard",
    response_model=list[LeaderboardEntry],
    summary="Public leaderboard ranked by wins",
)
async def get_leaderboard_endpoint(
    period: Annotated[
        str | None,
        Query(description="Time window filter: 'week' (7 days), 'month' (30 days), or omit for all-time"),
    ] = None,
    session: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntry]:
    """Return the top 50 human players sorted by total wins descending.

    - Excludes AI players from all results.
    - ``?period=week`` filters to games played in the last 7 days.
    - ``?period=month`` filters to games played in the last 30 days.
    - Omitting ``period`` (or ``period=all``) returns all-time stats.
    """
    # Validate the period parameter early so callers get a 400 with a clear
    # message rather than silently falling back to all-time.
    valid_periods = {"week", "month", "all"}
    if period is not None and period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period '{period}'. Must be one of: {sorted(valid_periods)}",
        )

    typed_period: Period | None = period if period in ("week", "month") else None  # type: ignore[assignment]
    try:
        return await get_leaderboard(session, period=typed_period)
    except Exception as exc:
        logger.exception("Failed to fetch leaderboard")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve leaderboard",
        ) from exc


# ---------------------------------------------------------------------------
# User scores router — requires authentication
# ---------------------------------------------------------------------------

user_scores_router = APIRouter(prefix="/api/users", tags=["users"])

_DEFAULT_LIMIT = 20
_MAX_LIMIT = 100


@user_scores_router.get(
    "/me/scores",
    response_model=ScoreHistoryResponse,
    summary="Current user's game history",
)
async def get_my_scores(
    limit: Annotated[
        int,
        Query(ge=1, le=_MAX_LIMIT, description="Page size (max 100)"),
    ] = _DEFAULT_LIMIT,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of records to skip"),
    ] = 0,
    current_user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
) -> ScoreHistoryResponse:
    """Return the authenticated user's game history with pagination.

    Sorted by most-recent game first. Use ``limit`` and ``offset`` for
    page-based navigation. The response includes ``total`` so clients can
    render pagination controls without a separate count request.
    """
    try:
        entries, total = await get_user_score_history(
            session, user_id=current_user_id, limit=limit, offset=offset
        )
    except Exception as exc:
        logger.exception("Failed to fetch score history for user %s", current_user_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve score history",
        ) from exc

    return ScoreHistoryResponse(
        entries=entries,
        total=total,
        limit=limit,
        offset=offset,
    )
