"""
Game engine for Ashta Chamma 3D.

Implements the server-authoritative game state machine derived from the
legacy helper.py and game.py rules.  This module is intentionally free
of I/O, async, or web-framework dependencies so it can be unit-tested
in isolation.

Color mapping (matches legacy code):
    R = 0, B = 1, G = 2, Y = 3

Board topology
--------------
The board is a 9×9 grid.  Each of the four players follows a 50-step
path (indices 0–49):
    index  0      — home position (off the inner board, border cell)
    indices 1–24  — outer shared track
    indices 25–49 — inner home-stretch (player-specific)
    index 49      — center square (4,4), the win destination

Rules (extracted from legacy helper.py / game.py):
    * Pawn release: a pawn at home (index 0) may only enter the board
      on a roll of 1 or 8.
    * Index-24 blocking: a pawn cannot cross from the outer track into
      the inner home-stretch (move to index > 24) unless the player has
      made at least one capture.  This is the "index-24 rule" referenced
      in the legacy move() function.
    * Overshoot prevention: a pawn cannot advance past the center
      (index 49).  The player must land on it exactly.
    * Friendly blocking: a pawn may not land on a square occupied by a
      friendly pawn unless that square is a safe square.
    * Capture: landing on an enemy pawn on a non-safe square sends that
      pawn back to its home (index 0) and grants the attacker an extra
      turn.
    * Extra turn on roll: rolls of 4 and 8 grant an extra turn
      (int(roll) % 4 == 0, from legacy game.py).
    * Win condition: a player wins when all four of their pawns reach
      the center (index 49).
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Board constants  (sourced from legacy path.py)
# ---------------------------------------------------------------------------

# Each player's ordered path of (row, col) board positions.
# index 0  = home position
# index 49 = center (4,4)
PATHS: list[list[tuple[int, int]]] = [
    # Color 0 (Red) — home at (0,4)
    [
        (0, 4), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1),
        (5, 1), (6, 1), (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6),
        (7, 7), (6, 7), (5, 7), (4, 7), (3, 7), (2, 7), (1, 7), (1, 6),
        (1, 5), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4),
        (6, 3), (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4),
        (2, 5), (3, 5), (4, 5), (5, 5), (5, 4), (5, 3), (4, 3), (3, 3),
        (3, 4), (4, 4),
    ],
    # Color 1 (Blue) — home at (4,0)
    [
        (4, 0), (4, 1), (5, 1), (6, 1), (7, 1), (7, 2), (7, 3), (7, 4),
        (7, 5), (7, 6), (7, 7), (6, 7), (5, 7), (4, 7), (3, 7), (2, 7),
        (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1),
        (3, 1), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6),
        (5, 6), (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2),
        (3, 2), (3, 3), (3, 4), (3, 5), (4, 5), (5, 5), (5, 4), (5, 3),
        (4, 3), (4, 4),
    ],
    # Color 2 (Green) — home at (8,4)
    [
        (8, 4), (7, 4), (7, 5), (7, 6), (7, 7), (6, 7), (5, 7), (4, 7),
        (3, 7), (2, 7), (1, 7), (1, 6), (1, 5), (1, 4), (1, 3), (1, 2),
        (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1), (7, 1), (7, 2),
        (7, 3), (6, 2), (5, 2), (4, 2), (3, 2), (2, 2), (2, 3), (2, 4),
        (2, 5), (2, 6), (3, 6), (4, 6), (5, 6), (6, 6), (6, 5), (6, 4),
        (6, 3), (5, 3), (4, 3), (3, 3), (3, 4), (3, 5), (4, 5), (5, 5),
        (5, 4), (4, 4),
    ],
    # Color 3 (Yellow) — home at (4,8)
    [
        (4, 8), (4, 7), (3, 7), (2, 7), (1, 7), (1, 6), (1, 5), (1, 4),
        (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1),
        (7, 1), (7, 2), (7, 3), (7, 4), (7, 5), (7, 6), (7, 7), (6, 7),
        (5, 7), (6, 6), (6, 5), (6, 4), (6, 3), (6, 2), (5, 2), (4, 2),
        (3, 2), (2, 2), (2, 3), (2, 4), (2, 5), (2, 6), (3, 6), (4, 6),
        (5, 6), (5, 5), (5, 4), (5, 3), (4, 3), (3, 3), (3, 4), (3, 5),
        (4, 5), (4, 4),
    ],
]

# Squares where pawns cannot be captured and any number of pawns may coexist.
SAFE_SQUARES: frozenset[tuple[int, int]] = frozenset({
    (1, 4), (2, 2), (2, 6), (4, 1), (4, 4), (4, 7), (6, 2), (6, 6), (7, 4),
})

# Roll values that allow a pawn at home to enter the board.
# Legacy game rule / architecture spec: only 1 and 8 unlock home entry.
RELEASE_ROLLS: frozenset[int] = frozenset({1, 8})

# Roll values that grant an extra turn without a capture.
# From legacy game.py: int(Num) % 4 == 0  →  4 and 8.
EXTRA_TURN_ROLLS: frozenset[int] = frozenset({4, 8})

# Index of the home position in every path.
HOME_INDEX: int = 0

# Index of the center (win destination) in every path.
CENTER_INDEX: int = 49

# Outer-track / inner-path boundary (legacy "index-24 rule").
# A pawn cannot advance past this index unless the player has made a capture.
INNER_PATH_THRESHOLD: int = 24

# Number of players.
NUM_PLAYERS: int = 4

# Pawns per player.
PAWNS_PER_PLAYER: int = 4


# ---------------------------------------------------------------------------
# Data-classes
# ---------------------------------------------------------------------------

@dataclass
class PawnState:
    """Represents a single pawn's location on the board."""

    color: int      # 0=R, 1=B, 2=G, 3=Y
    pawn_id: int    # 0–3 within that color group
    path_index: int  # 0 = home, 49 = center

    @property
    def position(self) -> tuple[int, int]:
        """Board coordinate (row, col) of this pawn."""
        return PATHS[self.color][self.path_index]

    @property
    def is_at_home(self) -> bool:
        """True when the pawn has not yet entered the board."""
        return self.path_index == HOME_INDEX

    @property
    def is_at_center(self) -> bool:
        """True when the pawn has reached the win destination."""
        return self.path_index == CENTER_INDEX


@dataclass
class GameState:
    """Complete, immutable-intent snapshot of a game in progress."""

    pawns: list[PawnState]
    current_player: int
    # Per-player flag tracking whether the player has captured at least once.
    # Required to cross the INNER_PATH_THRESHOLD (index-24 rule).
    kills_made: list[bool] = field(
        default_factory=lambda: [False] * NUM_PLAYERS
    )
    game_over: bool = False
    winner: Optional[int] = None

    def get_player_pawns(self, player: int) -> list[PawnState]:
        """Return all pawns that belong to *player*."""
        return [p for p in self.pawns if p.color == player]

    def get_pawn(self, color: int, pawn_id: int) -> PawnState:
        """Return the specific pawn; raises ValueError if not found."""
        for p in self.pawns:
            if p.color == color and p.pawn_id == pawn_id:
                return p
        raise ValueError(f"Pawn color={color} pawn_id={pawn_id} not found in state")


@dataclass
class MoveResult:
    """Outcome produced by GameSession.apply_move()."""

    new_state: GameState
    captured_pawn: Optional[PawnState]  # The captured enemy pawn, or None
    extra_turn: bool                    # True when current player rolls again
    game_over: bool                     # True when the move triggered a win


# ---------------------------------------------------------------------------
# Pure rule functions (unit-testable without a session)
# ---------------------------------------------------------------------------

def compute_new_path_index(
    pawn: PawnState,
    roll: int,
    kill_made: bool,
) -> int:
    """
    Compute the path index a pawn would reach after advancing *roll* steps.

    Returns the pawn's *current* path index when the move is not permitted
    (the pawn stays in place).

    Rules applied (in order):
    1. **Home-entry restriction** — a pawn at index 0 may only move if
       ``roll`` is in ``RELEASE_ROLLS`` (1 or 8).
    2. **Index-24 blocking** — a pawn on the outer track cannot enter the
       inner home-stretch (index > 24) unless *kill_made* is True.  This
       replicates the ``k+N > 24 and not isKill`` guard in legacy move().
    3. **Center overshoot prevention** — the pawn cannot advance past
       index 49; it must land there exactly.
    """
    k = pawn.path_index

    # Rule 1: home-entry restriction
    if k == HOME_INDEX and roll not in RELEASE_ROLLS:
        return k

    # Rule 2: index-24 blocking (legacy move() rule)
    if k + roll > INNER_PATH_THRESHOLD and not kill_made:
        return k

    # Rule 3: cannot overshoot center
    if k + roll > CENTER_INDEX:
        return k

    return k + roll


def get_possible_moves(state: GameState, roll: int) -> list[int]:
    """
    Return pawn_ids the current player may legally move with *roll*.

    Mirrors possibleMoves() from legacy helper.py, augmented with the
    new engine's home-entry restriction.

    A pawn is excluded when:
    - It is already at the center (already finished).
    - compute_new_path_index() would not change its position.
    - Its destination is occupied by a friendly pawn on a non-safe square.
    """
    current = state.current_player
    player_pawns = state.get_player_pawns(current)
    kill_made = state.kills_made[current]

    # Board positions currently occupied by THIS player's pawns.
    friendly_positions: set[tuple[int, int]] = {p.position for p in player_pawns}

    moveable: list[int] = []
    for pawn in player_pawns:
        if pawn.is_at_center:
            continue  # already finished; not a valid move target

        new_idx = compute_new_path_index(pawn, roll, kill_made)
        if new_idx == pawn.path_index:
            continue  # pawn does not actually move

        new_pos = PATHS[current][new_idx]

        # Friendly-blocking: cannot land on own pawn except on safe squares
        if new_pos in friendly_positions and new_pos not in SAFE_SQUARES:
            continue

        moveable.append(pawn.pawn_id)

    return moveable


# ---------------------------------------------------------------------------
# Game session
# ---------------------------------------------------------------------------

class GameSession:
    """
    Server-authoritative Ashta Chamma game session.

    Receives validated player actions (roll value + pawn selection) and
    produces state transitions according to the full rule set.
    """

    def __init__(self, state: GameState) -> None:
        self._state = state

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def state(self) -> GameState:
        """Current game state (read-only view; do not mutate directly)."""
        return self._state

    def get_possible_moves(self, roll: int) -> list[int]:
        """Return pawn_ids the current player can move with *roll*."""
        return get_possible_moves(self._state, roll)

    @staticmethod
    def is_extra_turn_roll(roll: int) -> bool:
        """True when *roll* grants an extra turn regardless of captures."""
        return roll in EXTRA_TURN_ROLLS

    def apply_move(self, pawn_id: int, roll: int) -> MoveResult:
        """
        Apply the selected pawn move and return a MoveResult.

        Steps:
        1. Advance the chosen pawn along its path.
        2. Detect and process captures (enemy pawn sent to home).
        3. Update the kills_made flag for the current player.
        4. Detect win condition (all 4 pawns at center).
        5. Determine whether the current player gets an extra turn
           (roll ∈ EXTRA_TURN_ROLLS  OR  a capture occurred).
        6. Advance current_player unless extra turn or game over.
        """
        new_state: GameState = copy.deepcopy(self._state)
        current: int = new_state.current_player
        pawn: PawnState = new_state.get_pawn(current, pawn_id)
        kill_made: bool = new_state.kills_made[current]

        # --- Move ---
        new_idx: int = compute_new_path_index(pawn, roll, kill_made)
        pawn.path_index = new_idx
        new_pos: tuple[int, int] = PATHS[current][new_idx]

        # --- Capture detection (non-safe squares only) ---
        captured: Optional[PawnState] = None
        if new_pos not in SAFE_SQUARES:
            for other in new_state.pawns:
                if other.color != current and other.position == new_pos:
                    # Send captured pawn back to its home position.
                    other.path_index = HOME_INDEX
                    captured = other
                    new_state.kills_made[current] = True
                    break

        # --- Win detection ---
        player_pawns = new_state.get_player_pawns(current)
        game_over = all(p.is_at_center for p in player_pawns)
        if game_over:
            new_state.game_over = True
            new_state.winner = current

        # --- Extra turn: roll-based OR capture-based ---
        extra_turn: bool = roll in EXTRA_TURN_ROLLS or captured is not None

        # --- Turn advancement ---
        if not extra_turn and not game_over:
            new_state.current_player = (current + 1) % NUM_PLAYERS

        self._state = new_state

        return MoveResult(
            new_state=new_state,
            captured_pawn=captured,
            extra_turn=extra_turn,
            game_over=game_over,
        )
