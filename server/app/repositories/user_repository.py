"""UserRepository — data-access layer for the ``users`` and ``game_scores`` tables.

All methods operate within the ``AsyncSession`` supplied at construction time.
Transaction management is the caller's responsibility.
"""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.game_score import GameScore
from app.models.user import User


class UserRepository:
    """Thin data-access wrapper — no business logic lives here."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_clerk_id(self, clerk_id: str) -> User | None:
        """Return the user whose ``clerk_id`` matches, or ``None``."""
        result = await self._session.execute(
            select(User).where(User.clerk_id == clerk_id)
        )
        return result.scalar_one_or_none()

    async def save(self, user: User) -> User:
        """Add or merge a user record and flush to the session."""
        self._session.add(user)
        await self._session.flush()
        return user

    async def nullify_game_scores(self, user_id: uuid.UUID) -> None:
        """Set ``user_id = NULL`` on every game_scores row linked to this user.

        Game data is retained for aggregate statistics; only the PII linkage
        is removed (GDPR recital 26 — anonymised data falls outside the
        regulation's scope).
        """
        await self._session.execute(
            update(GameScore)
            .where(GameScore.user_id == user_id)
            .values(user_id=None)
        )
