"""Server-authoritative game state machine for Ashta Chamma.

States and transitions
----------------------
::

    WAITING
      │  start_game()
      ▼
    ROLLING  ◄──────────────────────────────────────────────────────┐
      │  apply_roll()                                                │
      │  ├─ no legal moves ──► advance turn ──► ROLLING (next)     │
      │  └─ legal moves exist                                        │
      ▼                                                              │
    SELECTING                                                        │
      │  apply_move()                                                │
      ▼                                                              │
    MOVING                                                           │
      │  confirm_move()                                              │
      │  ├─ win condition ──► GAME_OVER                             │
      │  ├─ extra turn     ──► ROLLING (same player) ──────────────┘
      └─ normal turn     ──► ROLLING (next player) ────────────────┘

The MOVING state exists so callers (e.g. WebSocket handlers) can broadcast a
move animation event before the next ROLLING prompt is issued.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .board import NUM_PLAYERS, PATHS, PAWNS_PER_PLAYER, SAFE_SQUARES, WIN_PATH_INDEX
from .dice import CowrieRoll, EXTRA_TURN_VALUES
from .moves import Move, compute_legal_moves


# ---------------------------------------------------------------------------
# State enum
# ---------------------------------------------------------------------------


class GameState(Enum):
    """Finite states of a game session."""

    WAITING = "WAITING"
    ROLLING = "ROLLING"
    SELECTING = "SELECTING"
    MOVING = "MOVING"
    GAME_OVER = "GAME_OVER"


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class GameError(Exception):
    """Raised when a caller attempts an action that is illegal in the current state."""


# ---------------------------------------------------------------------------
# Move result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MoveResult:
    """Outcome of a single pawn move, computed by :meth:`GameSession.apply_move`.

    Attributes:
        captured: True if an opponent pawn was sent back to home.
        winner: Player index if the move triggered a win, else ``None``.
        extra_turn: True if the moving player should roll again.
    """

    captured: bool
    winner: Optional[int]
    extra_turn: bool


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


@dataclass
class GameSession:
    """Mutable server-side game session.

    All public methods enforce valid state transitions.  Callers receive a
    :class:`GameError` for any action that violates the current state or turn
    order, making it straightforward to return ``NOT_YOUR_TURN`` / ``INVALID_MOVE``
    errors to clients.

    Attributes:
        session_id: Opaque identifier for this game session.
        pawn_positions: ``pawn_positions[player][pawn]`` → path index.
            0 means the pawn is at home (not yet in play).
            WIN_PATH_INDEX means the pawn has reached the centre (won).
        current_player: Index of the player whose turn it is (0–3).
        state: Current :class:`GameState`.
        last_roll: Value from the most recent cowrie throw (or ``None``).
        winner: Player index of the winner, populated on reaching GAME_OVER.
        legal_moves: Legal moves computed after the last roll.
    """

    session_id: str
    pawn_positions: list[list[int]] = field(
        default_factory=lambda: [[0] * PAWNS_PER_PLAYER for _ in range(NUM_PLAYERS)]
    )
    current_player: int = 0
    state: GameState = GameState.WAITING
    last_roll: Optional[int] = None
    winner: Optional[int] = None
    legal_moves: list[Move] = field(default_factory=list)
    _pending_result: Optional[MoveResult] = field(default=None, repr=False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_game(self) -> None:
        """Transition WAITING → ROLLING.

        Raises:
            GameError: If the session is not in WAITING state.
        """
        self._require_state(GameState.WAITING)
        self.state = GameState.ROLLING

    def apply_roll(self, roll: CowrieRoll, player_index: Optional[int] = None) -> list[Move]:
        """Process a cowrie roll and compute legal moves.

        Transitions ROLLING → SELECTING (when moves exist) or
        ROLLING → ROLLING (next player, when no moves exist).

        Args:
            roll: The cowrie roll result.
            player_index: Optional — if supplied, validated against
                ``current_player`` so callers can detect wrong-turn errors.

        Returns:
            The list of legal :class:`Move` objects.  Empty when the turn
            passes automatically.

        Raises:
            GameError: If the session is not in ROLLING state, or if
                ``player_index`` does not match the current player.
        """
        self._require_state(GameState.ROLLING)
        if player_index is not None and player_index != self.current_player:
            raise GameError(
                f"It is player {self.current_player}'s turn, not player {player_index}'s."
            )

        self.last_roll = roll.value
        moves = compute_legal_moves(
            self.current_player,
            tuple(self.pawn_positions[self.current_player]),
            tuple(tuple(p) for p in self.pawn_positions),
            roll.value,
        )

        if not moves:
            # No legal moves — pass turn to next player.
            self._advance_turn()
            return []

        self.legal_moves = moves
        self.state = GameState.SELECTING
        return moves

    def apply_move(self, player_index: int, pawn_index: int) -> MoveResult:
        """Select and execute a pawn move.

        Transitions SELECTING → MOVING.  The caller must then invoke
        :meth:`confirm_move` to complete the turn.

        Args:
            player_index: The player attempting the move.  Must equal
                ``current_player``.
            pawn_index: Which pawn (0–3) to move.

        Returns:
            A :class:`MoveResult` describing the outcome.

        Raises:
            GameError: If the state is not SELECTING, if it is not the
                player's turn, or if pawn_index has no legal move.
        """
        self._require_state(GameState.SELECTING)
        if player_index != self.current_player:
            raise GameError(
                f"It is player {self.current_player}'s turn, not player {player_index}'s."
            )

        matching = [m for m in self.legal_moves if m.pawn_index == pawn_index]
        if not matching:
            raise GameError(
                f"Pawn {pawn_index} of player {player_index} has no legal move this turn."
            )

        move = matching[0]
        self.pawn_positions[self.current_player][pawn_index] = move.to_path_index

        # Resolve capture.
        captured = self._resolve_capture(self.current_player, move.to_path_index)

        # Determine whether the player earns an extra turn.
        extra_turn = (self.last_roll in EXTRA_TURN_VALUES) or captured

        # Check win condition.
        win = self._check_win(self.current_player)
        winning_player: Optional[int] = self.current_player if win else None

        result = MoveResult(captured=captured, winner=winning_player, extra_turn=extra_turn)
        self._pending_result = result
        self.legal_moves = []
        self.state = GameState.MOVING
        return result

    def confirm_move(self) -> None:
        """Finalise the MOVING phase and transition to the next state.

        Transitions:
          * MOVING → GAME_OVER  (if the last move triggered a win)
          * MOVING → ROLLING    (same player if extra turn)
          * MOVING → ROLLING    (next player otherwise)

        Raises:
            GameError: If the session is not in MOVING state.
        """
        self._require_state(GameState.MOVING)
        assert self._pending_result is not None, "confirm_move called without a pending result"

        result = self._pending_result
        self._pending_result = None

        if result.winner is not None:
            self.winner = result.winner
            self.state = GameState.GAME_OVER
            return

        if result.extra_turn:
            # Same player rolls again.
            self.state = GameState.ROLLING
        else:
            self._advance_turn()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_state(self, expected: GameState) -> None:
        if self.state != expected:
            raise GameError(
                f"Action requires state {expected.value} but current state is {self.state.value}."
            )

    def _resolve_capture(self, attacker: int, new_path_index: int) -> bool:
        """Check for a capture at the attacker's new position.

        Captures are only possible on non-safe squares.  If an opponent pawn
        shares the physical square, it is sent back to home (path index 0).

        Returns:
            True if a capture occurred.
        """
        target_sq = PATHS[attacker][new_path_index]

        # Safe squares are immune to capture.
        if target_sq in SAFE_SQUARES:
            return False

        for p in range(NUM_PLAYERS):
            if p == attacker:
                continue
            for j in range(PAWNS_PER_PLAYER):
                pi = self.pawn_positions[p][j]
                # Pawns at home or at centre cannot be captured on the outer track.
                if pi == 0 or pi == WIN_PATH_INDEX:
                    continue
                if PATHS[p][pi] == target_sq:
                    self.pawn_positions[p][j] = 0  # send home
                    return True

        return False

    def _check_win(self, player: int) -> bool:
        """Return True if all of *player*'s pawns are on the centre square."""
        return all(idx == WIN_PATH_INDEX for idx in self.pawn_positions[player])

    def _advance_turn(self) -> None:
        """Move to the next player in round-robin order and enter ROLLING."""
        self.current_player = (self.current_player + 1) % NUM_PLAYERS
        self.state = GameState.ROLLING
