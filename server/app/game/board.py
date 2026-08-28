"""Board constants for Ashta Chamma.

The board is a 9×9 grid. This module centralises all positional constants
so game logic modules can import them without duplicating data.

Home positions are derived from the legacy player.py initialisation:
  Player 0 (red):    cells[0][4]  → (0, 4)
  Player 1 (blue):   cells[4][0]  → (4, 0)
  Player 2 (green):  cells[8][4]  → (8, 4)
  Player 3 (yellow): cells[4][8]  → (4, 8)
"""

from typing import Final

# Canonical turn order — index matches player_index in the DB.
PLAYER_COLORS: Final[list[str]] = ["red", "blue", "green", "yellow"]

# Home (base) positions per player on the 9×9 grid.
# Pawns sit here before entering the main track.
HOME_POSITIONS: Final[dict[str, tuple[int, int]]] = {
    "red": (0, 4),
    "blue": (4, 0),
    "green": (8, 4),
    "yellow": (4, 8),
}

# Squares marked as safe (cross symbol in legacy UI).
# Pawns on these squares cannot be captured.
SAFE_SQUARES: Final[list[tuple[int, int]]] = [
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

# Shared destination square — reaching (4, 4) means a pawn has finished.
GOAL_SQUARE: Final[tuple[int, int]] = (4, 4)

# Fixed number of pawns each player controls.
PAWNS_PER_PLAYER: Final[int] = 4
