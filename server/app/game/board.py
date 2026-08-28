"""Board topology and path data for Ashta Chamma (WO-011).

This module is a pure-data, framework-agnostic representation of the 9×9
cross-shaped game board.  All coordinates are (row, col) tuples.

Path layout
-----------
Each player has a 50-square *full path* starting at their home base:

    full_path[0]     – home base (pen entry square, row/col on board edge)
    full_path[1..24] – shared outer track (24 squares)
    full_path[25..49]– player-specific home stretch leading to (4,4)

The ``TRACK_PATHS`` exported from this module strip the home-base square so
that path_index=0 is the first square *on* the playing track and
path_index=48 is the win position (4,4).  path_index=-1 is used by
``GameSession`` to represent a pawn still in the home pen.

Constants
---------
HOME_STRETCH_START  : int = 24  – track index where the home stretch begins
WIN_TRACK_INDEX     : int = 48  – track index of the shared centre (4,4)
PAWN_ENTRY_ROLLS    : frozenset – roll values that allow a home pawn to enter
EXTRA_TURN_ROLLS    : frozenset – roll values that grant an extra turn
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Raw 50-element paths (ported verbatim from legacy path.py).
# Index 0 = player home base; indices 1-49 = playing track.
# ---------------------------------------------------------------------------

_RAW_PATHS: list[list[tuple[int, int]]] = [
    # Player 0 – RED  (home base (0,4))
    [
        (0, 4),
        (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1),
        (6, 1), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7),
        (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7), (1, 6), (1, 5),
        (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4), (6, 3),
        (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4), (2, 5),
        (3, 5), (4, 5), (5, 5), (5, 4), (5, 3), (4, 3), (3, 3), (3, 4),
        (4, 4),
    ],
    # Player 1 – BLUE  (home base (4,0))
    [
        (4, 0),
        (4, 1), (5, 1), (6, 1), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5),
        (7, 6), (7, 7), (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7),
        (1, 6), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1),
        (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6), (5, 6),
        (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2), (3, 2),
        (3, 3), (3, 4), (3, 5), (4, 5), (5, 5), (5, 4), (5, 3), (4, 3),
        (4, 4),
    ],
    # Player 2 – GREEN  (home base (8,4))
    [
        (8, 4),
        (7, 4), (7, 5), (7, 6), (7, 7), (6, 7), (5, 7), (4, 7), (3, 7),
        (2, 7), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1),
        (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (7, 2), (7, 3),
        (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4), (2, 5),
        (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4), (6, 3),
        (5, 3), (4, 3), (3, 3), (3, 4), (3, 5), (4, 5), (5, 5), (5, 4),
        (4, 4),
    ],
    # Player 3 – YELLOW  (home base (4,8))
    [
        (4, 8),
        (4, 7), (3, 7), (2, 7), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3),
        (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1),
        (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (6, 7), (5, 7),
        (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2), (3, 2),
        (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6), (5, 6),
        (5, 5), (5, 4), (5, 3), (4, 3), (3, 3), (3, 4), (3, 5), (4, 5),
        (4, 4),
    ],
]

# ---------------------------------------------------------------------------
# Derived data structures
# ---------------------------------------------------------------------------

# Track paths: strip home-base square → 49 elements (index 0..48)
TRACK_PATHS: list[list[tuple[int, int]]] = [p[1:] for p in _RAW_PATHS]

# Home (pen) board coordinate for each player (raw path index 0)
HOME_POSITIONS: list[tuple[int, int]] = [p[0] for p in _RAW_PATHS]

# Safe squares: pawns here cannot be captured and multiple pawns may stack
SAFE_SQUARES: frozenset[tuple[int, int]] = frozenset(
    {(1, 4), (2, 2), (2, 6), (4, 1), (4, 4), (4, 7), (6, 2), (6, 6), (7, 4)}
)

# ---------------------------------------------------------------------------
# Game-rule constants
# ---------------------------------------------------------------------------

#: Track index at which the player-specific home stretch begins.
HOME_STRETCH_START: int = 24

#: Track index of the shared win square (4,4).
WIN_TRACK_INDEX: int = 48

#: Roll values that allow a pawn to leave the home pen.
PAWN_ENTRY_ROLLS: frozenset[int] = frozenset({1, 8})

#: Roll values that grant the current player an extra turn.
EXTRA_TURN_ROLLS: frozenset[int] = frozenset({1, 4, 8})

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def get_track_position(color_index: int, path_index: int) -> tuple[int, int]:
    """Return the board coordinates for a given player and track path index.

    Args:
        color_index: Integer 0-3 matching ``PlayerColor`` value.
        path_index: Track index 0..48.

    Returns:
        Board coordinates ``(row, col)``.

    Raises:
        IndexError: If ``path_index`` is outside 0..48.
    """
    return TRACK_PATHS[color_index][path_index]


def is_safe_square(position: tuple[int, int]) -> bool:
    """Return True if *position* is a safe square (no captures allowed)."""
    return position in SAFE_SQUARES


def get_home_position(color_index: int) -> tuple[int, int]:
    """Return the home-pen board coordinates for *color_index*."""
    return HOME_POSITIONS[color_index]
