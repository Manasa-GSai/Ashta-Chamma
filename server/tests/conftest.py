"""Shared pytest fixtures for the Ashta Chamma server test suite.

Fixtures defined here are available to all tests without explicit imports.
All fixtures that involve game state use seeded random generators so test
runs are deterministic.
"""

from __future__ import annotations

import random

import pytest

from app.game.dice import CowrieRoll, make_roll
from app.game.state_machine import GameSession, GameState


# ---------------------------------------------------------------------------
# RNG fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_rng() -> random.Random:
    """A deterministic ``random.Random`` instance seeded to 42."""
    return random.Random(42)


# ---------------------------------------------------------------------------
# Game session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fresh_session() -> GameSession:
    """A brand-new game session in WAITING state."""
    return GameSession(session_id="test-session-001")


@pytest.fixture()
def rolling_session() -> GameSession:
    """A game session that has been started (ROLLING state, player 0's turn)."""
    session = GameSession(session_id="test-session-002")
    session.start_game()
    return session


@pytest.fixture()
def selecting_session() -> GameSession:
    """A game session in SELECTING state.

    Player 0 has rolled an 8 (which allows pawn release).  All pawns are
    still at home so there will be legal release moves available.
    """
    session = GameSession(session_id="test-session-003")
    session.start_game()
    session.apply_roll(make_roll(8))
    return session


@pytest.fixture()
def mid_game_session() -> GameSession:
    """A session with player 0's first pawn well into the board.

    Player 0, pawn 0 is at path index 10 (a non-safe outer track square).
    All other pawns are at home.  Session is in ROLLING state ready for
    player 0 to roll again.
    """
    session = GameSession(session_id="test-session-004")
    session.start_game()
    # Manually advance pawn 0 of player 0 to path index 10.
    session.pawn_positions[0][0] = 10
    return session
