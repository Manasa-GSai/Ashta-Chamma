"""Board topology constants for the Ashta Chamma game.

This module is intentionally a pure-constant module with zero side effects.
All values are derived from the original pygame implementation and cross-
checked against the legacy path.py and game.py sources.

Board layout: 9×9 grid. Only inner cells (1–7, 1–7) and the four edge
"home base" cells are active. Each player has a 50-step path:
  index 0  → home base (pawn not yet in play)
  index 1–24 → shared outer track (counterclockwise)
  index 25–48 → player-specific inner home stretch
  index 49 → centre square (4,4) — pawn has won
"""

from typing import Final

# ---------------------------------------------------------------------------
# Player / pawn counts
# ---------------------------------------------------------------------------

NUM_PLAYERS: Final[int] = 4
PAWNS_PER_PLAYER: Final[int] = 4

# ---------------------------------------------------------------------------
# Board dimensions
# ---------------------------------------------------------------------------

BOARD_SIZE: Final[int] = 9

# ---------------------------------------------------------------------------
# Special squares
# ---------------------------------------------------------------------------

# Safe squares: pawns on these squares are immune to capture.
# The centre (4,4) is included — it doubles as a safe square.
SAFE_SQUARES: Final[frozenset[tuple[int, int]]] = frozenset(
    [
        (1, 4),
        (2, 2),
        (2, 6),
        (4, 1),
        (4, 4),
        (4, 7),
        (6, 2),
        (6, 6),
        (7, 4),
    ]
)

# Home base positions for each player.
# A pawn starts here and is considered "not yet in play" (path index 0).
HOME_POSITIONS: Final[tuple[tuple[int, int], ...]] = (
    (0, 4),  # Player 0
    (4, 0),  # Player 1
    (8, 4),  # Player 2
    (4, 8),  # Player 3
)

# The winning square — a pawn that reaches here has finished.
CENTER: Final[tuple[int, int]] = (4, 4)

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

# Total number of squares in each player's path (including home and centre).
PATH_LENGTH: Final[int] = 50

# Path index at which a pawn is considered to have won.
WIN_PATH_INDEX: Final[int] = 49

# First path index that belongs to the player-specific home stretch.
# Indices 25–48 are the inner spiral; index 49 is the centre.
HOME_STRETCH_START: Final[int] = 25

# ---------------------------------------------------------------------------
# Movement paths
# ---------------------------------------------------------------------------
# Each tuple has exactly 50 entries:
#   [0]  = home base (off-board starting square)
#   [1–24] = shared outer track
#   [25–48] = player-specific inner stretch
#   [49] = centre square (4,4)
#
# Source: legacy path.py — values reproduced verbatim.

PATHS: Final[tuple[tuple[tuple[int, int], ...], ...]] = (
    # ------------------------------------------------------------------ #
    # Player 0 — home base at (0,4)                                       #
    # ------------------------------------------------------------------ #
    (
        (0, 4),
        (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1),
        (6, 1), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7),
        (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7), (1, 6), (1, 5),
        # home stretch
        (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4), (6, 3),
        (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4), (2, 5),
        (3, 5), (4, 5), (5, 5), (5, 4), (5, 3), (4, 3), (3, 3), (3, 4),
        (4, 4),
    ),
    # ------------------------------------------------------------------ #
    # Player 1 — home base at (4,0)                                       #
    # ------------------------------------------------------------------ #
    (
        (4, 0),
        (4, 1), (5, 1), (6, 1), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5),
        (7, 6), (7, 7), (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7),
        (1, 6), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1),
        # home stretch
        (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6), (5, 6),
        (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2), (3, 2),
        (3, 3), (3, 4), (3, 5), (4, 5), (5, 5), (5, 4), (5, 3), (4, 3),
        (4, 4),
    ),
    # ------------------------------------------------------------------ #
    # Player 2 — home base at (8,4)                                       #
    # ------------------------------------------------------------------ #
    (
        (8, 4),
        (7, 4), (7, 5), (7, 6), (7, 7), (6, 7), (5, 7), (4, 7), (3, 7),
        (2, 7), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1),
        (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (7, 2), (7, 3),
        # home stretch
        (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4), (2, 5),
        (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4), (6, 3),
        (5, 3), (4, 3), (3, 3), (3, 4), (3, 5), (4, 5), (5, 5), (5, 4),
        (4, 4),
    ),
    # ------------------------------------------------------------------ #
    # Player 3 — home base at (4,8)                                       #
    # ------------------------------------------------------------------ #
    (
        (4, 8),
        (4, 7), (3, 7), (2, 7), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3),
        (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1),
        (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (6, 7), (5, 7),
        # home stretch
        (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2), (3, 2),
        (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6), (5, 6),
        (5, 5), (5, 4), (5, 3), (4, 3), (3, 3), (3, 4), (3, 5), (4, 5),
        (4, 4),
    ),
)
