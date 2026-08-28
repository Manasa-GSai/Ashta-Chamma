"""Data models for the Ashta Chamma game engine.

These are framework-agnostic dataclasses shared across the game package.
No FastAPI or SQLAlchemy imports belong here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class PlayerColor(IntEnum):
    """Maps to the four players: RED=0, BLUE=1, GREEN=2, YELLOW=3.

    Integer values match the legacy game.py color indices so the two
    codebases stay interoperable during migration.
    """

    RED = 0
    BLUE = 1
    GREEN = 2
    YELLOW = 3


@dataclass
class RollResult:
    """Result of a single cowrie-shell throw.

    Attributes:
        value: Effective move distance (1, 2, 3, 4, or 8).
               0 face-up cowries → value 8 (Ashta).
        cowries: Boolean state for each of the 4 shells (True = face-up).
        grants_extra_turn: True when value is 1, 4, or 8.
    """

    value: int
    cowries: list[bool]
    grants_extra_turn: bool


@dataclass
class Pawn:
    """A single game pawn.

    Attributes:
        id: Globally unique identifier 0-15 (color_index * 4 + pawn_number).
        color: Which player owns this pawn.
        path_index: Position on the player's 49-square track (0..48),
                    or -1 when the pawn is in the home pen (not yet entered).
        position: Current board coordinates as (row, col).  Updated by
                  GameSession whenever path_index changes.
    """

    id: int
    color: PlayerColor
    path_index: int = field(default=-1)
    position: tuple[int, int] = field(default=(0, 0))
