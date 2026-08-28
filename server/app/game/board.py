"""Board topology and path data for Ashta Chamma.

This module is the single source of truth for all static board constants used
by the game engine.  It defines:

- :data:`PlayerColor` — canonical color-to-index mapping (0=Red, 1=Blue,
  2=Green, 3=Yellow), matching legacy ``path.py`` behavior.
- :data:`CENTER` — the winning/center square ``(4, 4)``.
- :data:`SAFE_SQUARES` — frozenset of squares where pawns cannot be captured.
- :data:`HOME_POSITIONS` — each player's starting square (before entering the
  shared track).
- :data:`PATHS` — ordered spiral paths from each player's home position to the
  center.  Each path is a ``list[tuple[int, int]]`` of ``(row, col)`` pairs on
  the 9 × 9 grid (rows and columns 0–8).

Board layout
------------
The board is cross-shaped on a 9 × 9 grid.  The corner 3 × 3 regions are
off-track (black squares).  Each player's pawn begins at their *home position*
(an edge square of the cross) and travels along a 49-step spiral inward to the
center at ``(4, 4)``.

Player home positions::

    Player 0 (Red)    → (0, 4)  — top edge, center column
    Player 1 (Blue)   → (4, 0)  — left edge, center row
    Player 2 (Green)  → (8, 4)  — bottom edge, center column
    Player 3 (Yellow) → (4, 8)  — right edge, center row

Color mapping note
------------------
The legacy ``path.py`` uses **R=0, B=1, G=2, Y=3**.  The README describes a
different ordering (R→B→Y→G).  This module intentionally preserves the legacy
code behavior (not the README) to avoid rule regression in the ported engine.

Path structure
--------------
Each path has exactly 49 steps.  The first element is the player's home
position; the last element is always ``CENTER == (4, 4)``.  The paths share
a long outer loop around the cross perimeter before branching inward along a
player-specific spiral toward the center.

Validation
----------
:func:`validate_paths` is called automatically at module import and raises
:class:`ValueError` if the path data is ever corrupted.

Grid bounds
-----------
All coordinates are ``(row, col)`` with ``0 ≤ row ≤ 8`` and
``0 ≤ col ≤ 8``.
"""

from enum import IntEnum


# ---------------------------------------------------------------------------
# Color constants
# ---------------------------------------------------------------------------


class PlayerColor(IntEnum):
    """Canonical mapping of player color to integer index.

    Matches the legacy ``path.py`` / ``game.py`` ordering: 0=Red, 1=Blue,
    2=Green, 3=Yellow.  The README listed a different sequence (R→B→Y→G);
    this enum preserves the code behavior to avoid rule regression.
    """

    RED = 0
    BLUE = 1
    GREEN = 2
    YELLOW = 3


# ---------------------------------------------------------------------------
# Board-level constants
# ---------------------------------------------------------------------------

CENTER: tuple[int, int] = (4, 4)
"""The winning square at the center of the board."""

SAFE_SQUARES: frozenset[tuple[int, int]] = frozenset(
    {
        (1, 4),
        (2, 2),
        (2, 6),
        (4, 1),
        (4, 4),
        (4, 7),
        (6, 2),
        (6, 6),
        (7, 4),
    }
)
"""Squares where pawns are immune to capture.

Includes the center (4, 4) and the eight entry/anchor points of the spiral
arms.  A pawn on a safe square cannot be sent back to its home base even if
an opponent pawn lands on the same square.
"""

HOME_POSITIONS: dict[PlayerColor, tuple[int, int]] = {
    PlayerColor.RED: (0, 4),
    PlayerColor.BLUE: (4, 0),
    PlayerColor.GREEN: (8, 4),
    PlayerColor.YELLOW: (4, 8),
}
"""Each player's home (starting) square before entering the shared track.

Ported from the ``home_places`` list in ``helper.py`` / ``game.py``.
The ordering in those files was ``[(4,8), (8,4), (4,0), (0,4)]`` which
corresponds to Yellow(3), Green(2), Blue(1), Red(0) by the color index —
this dict makes the association explicit and unambiguous.
"""

# ---------------------------------------------------------------------------
# Path data — ported verbatim from legacy path.py
# ---------------------------------------------------------------------------

PATHS: dict[PlayerColor, list[tuple[int, int]]] = {
    PlayerColor.RED: [
        (0, 4), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1),
        (5, 1), (6, 1), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6),
        (7, 7), (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7), (1, 6),
        (1, 5), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4),
        (6, 3), (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4),
        (2, 5), (3, 5), (4, 5), (5, 5), (5, 4), (5, 3), (4, 3), (3, 3),
        (3, 4), (4, 4),
    ],
    PlayerColor.BLUE: [
        (4, 0), (4, 1), (5, 1), (6, 1), (7, 1), (7, 2), (7, 3), (7, 4),
        (7, 5), (7, 6), (7, 7), (6, 7), (5, 7), (4, 7), (3, 7), (2, 7),
        (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1),
        (3, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6),
        (5, 6), (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2),
        (3, 2), (3, 3), (3, 4), (3, 5), (4, 5), (5, 5), (5, 4), (5, 3),
        (4, 3), (4, 4),
    ],
    PlayerColor.GREEN: [
        (8, 4), (7, 4), (7, 5), (7, 6), (7, 7), (6, 7), (5, 7), (4, 7),
        (3, 7), (2, 7), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2),
        (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (7, 2),
        (7, 3), (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4),
        (2, 5), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4),
        (6, 3), (5, 3), (4, 3), (3, 3), (3, 4), (3, 5), (4, 5), (5, 5),
        (5, 4), (4, 4),
    ],
    PlayerColor.YELLOW: [
        (4, 8), (4, 7), (3, 7), (2, 7), (1, 7), (1, 6), (1, 5), (1, 4),
        (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
        (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (6, 7),
        (5, 7), (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2),
        (3, 2), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6),
        (5, 6), (5, 5), (5, 4), (5, 3), (4, 3), (3, 3), (3, 4), (3, 5),
        (4, 5), (4, 4),
    ],
}
"""Ordered spiral paths for each player from home to center.

Each path is a ``list[tuple[int, int]]`` of ``(row, col)`` squares.  Index 0
is the player's home position; the final element is always ``CENTER (4, 4)``.

The coordinate sequences are ported verbatim from the legacy ``path.py`` to
preserve exact game-rule fidelity.
"""

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

_GRID_MIN: int = 0
_GRID_MAX: int = 8
_EXPECTED_PATH_LENGTH: int = 50


def validate_paths() -> None:
    """Validate all path data at import time.

    Checks performed for each player path:

    1. **Length** — must be exactly :data:`_EXPECTED_PATH_LENGTH` (50) steps.
    2. **Bounds** — every coordinate must satisfy
       ``0 ≤ row ≤ 8`` and ``0 ≤ col ≤ 8``.
    3. **No duplicates** — each coordinate must appear at most once per path.
    4. **Ends at center** — the last element must equal :data:`CENTER`.

    Raises:
        ValueError: If any of the above checks fail, with a descriptive
            message indicating which player and what was wrong.
    """
    for color in PlayerColor:
        path = PATHS[color]
        name = color.name

        # 1. Length check
        if len(path) != _EXPECTED_PATH_LENGTH:
            raise ValueError(
                f"Path for {name} has {len(path)} steps; "
                f"expected {_EXPECTED_PATH_LENGTH}."
            )

        # 2. Bounds check
        for idx, (row, col) in enumerate(path):
            if not (_GRID_MIN <= row <= _GRID_MAX and _GRID_MIN <= col <= _GRID_MAX):
                raise ValueError(
                    f"Path for {name}, step {idx}: coordinate ({row}, {col}) "
                    f"is out of the 9×9 grid bounds."
                )

        # 3. Duplicate check
        seen: set[tuple[int, int]] = set()
        for idx, coord in enumerate(path):
            if coord in seen:
                raise ValueError(
                    f"Path for {name} contains duplicate coordinate {coord} "
                    f"at step {idx}."
                )
            seen.add(coord)

        # 4. Terminal square check
        if path[-1] != CENTER:
            raise ValueError(
                f"Path for {name} does not end at CENTER {CENTER}; "
                f"last square is {path[-1]}."
            )


# Run validation eagerly so any corruption is caught at import time rather
# than silently producing incorrect game results later.
validate_paths()
