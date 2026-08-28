"""Ashta Chamma server-side game logic package.

Provides board topology constants, cowrie roll engine, move validation, and
the authoritative game state machine. All sub-modules are pure Python with no
external dependencies, making them straightforward to unit-test in isolation.
"""

from .board import PATHS, SAFE_SQUARES, HOME_POSITIONS, CENTER, WIN_PATH_INDEX
from .dice import CowrieRoll, roll_cowries, EXTRA_TURN_VALUES, RELEASE_VALUES
from .moves import Move, compute_legal_moves
from .state_machine import GameSession, GameState, GameError, MoveResult

__all__ = [
    "PATHS",
    "SAFE_SQUARES",
    "HOME_POSITIONS",
    "CENTER",
    "WIN_PATH_INDEX",
    "CowrieRoll",
    "roll_cowries",
    "EXTRA_TURN_VALUES",
    "RELEASE_VALUES",
    "Move",
    "compute_legal_moves",
    "GameSession",
    "GameState",
    "GameError",
    "MoveResult",
]
