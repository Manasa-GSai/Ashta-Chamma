"""Server-side finite state machine (FSM) for Ashta Chamma (WO-013).

Game lifecycle
--------------
::

    WAITING ──start_game()──► ROLLING
                                 │ roll() – legal moves exist
                                 ▼
                             SELECTING
                                 │ select_pawn(pawn_id)
                                 ▼
                             MOVING ──────── capture? ──► CAPTURING ──┐
                                 │                                     │
                                 └─────────── no capture ──────────────┘
                                 │
                       extra turn?│
                         ┌────Yes─┘
                         ▼         ▼
                      ROLLING    ROLLING (next player)
                         │
                  win condition?
                         │
                         ▼
                      GAME_OVER

Extra-turn rule
    The current player rolls again on a roll value of 1, 4, or 8 **and**
    on any capture.  The two sources are OR'd: either grants the extra turn.

Home-stretch rule
    A player must have captured at least one opponent pawn before any of
    their pawns may enter the home stretch (track indices 24-48).

Pawn-release rule
    A pawn in the home pen (path_index == -1) may only enter the board on a
    roll of 1 or 8.

Determinism
    ``GameSession`` accepts an optional ``random.Random`` instance so callers
    can inject a seeded generator for deterministic testing.
"""

from __future__ import annotations

import logging
import random
from enum import Enum, auto
from typing import Any, Optional

from app.game.board import (
    HOME_STRETCH_START,
    PAWN_ENTRY_ROLLS,
    WIN_TRACK_INDEX,
    get_home_position,
    get_track_position,
    is_safe_square,
)
from app.game.dice import roll_cowries
from app.game.exceptions import InvalidActionError, InvalidStateTransitionError
from app.game.models import Pawn, PlayerColor, RollResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FSM state enumeration
# ---------------------------------------------------------------------------


class GameState(Enum):
    """Exhaustive set of states the Ashta Chamma FSM may occupy."""

    WAITING = auto()
    ROLLING = auto()
    SELECTING = auto()
    MOVING = auto()
    CAPTURING = auto()
    GAME_OVER = auto()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_PAWNS_PER_PLAYER = 4
_NUM_PLAYERS = 4


def _pawn_id(color_index: int, pawn_number: int) -> int:
    """Return the globally-unique pawn ID (0-15)."""
    return color_index * _PAWNS_PER_PLAYER + pawn_number


# ---------------------------------------------------------------------------
# GameSession
# ---------------------------------------------------------------------------


class GameSession:
    """Server-authoritative game engine for a single Ashta Chamma session.

    All mutable state lives inside this object.  Clients send *intents*
    (roll, select_pawn) and receive validated state snapshots via
    ``events``.

    Attributes:
        state: Current FSM state.
        pawns: Mapping of pawn_id (0-15) → :class:`~app.game.models.Pawn`.
        current_player_index: Index 0-3 of the player who must act next.
        current_roll: The :class:`~app.game.models.RollResult` from the most
            recent roll, or ``None`` before the first roll.
        legal_moves: Pawn IDs that may be moved on the current roll.
        board: Mapping of board position ``(row,col)`` → list of pawn IDs
            currently occupying that square.
        roll_history: All ``RollResult`` objects in chronological order.
        events: State-change events accumulated since the last external
            read.  WebSocket handlers should drain this list after each
            client action.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, rng: Optional[random.Random] = None) -> None:
        """Create a new session in the WAITING state.

        Args:
            rng: Optional seeded ``random.Random`` for deterministic tests.
                 ``None`` uses the cryptographically secure default.
        """
        self._rng = rng
        self.state: GameState = GameState.WAITING
        self.current_player_index: int = 0
        self.current_roll: Optional[RollResult] = None
        self.legal_moves: list[int] = []
        self.roll_history: list[RollResult] = []
        self.events: list[dict[str, Any]] = []

        # Per-player flag: True once the player has captured an opponent pawn.
        # Required before the player may enter their home stretch.
        self._player_has_captured: list[bool] = [False] * _NUM_PLAYERS

        # Whether the current roll value alone (1, 4, 8) grants an extra turn.
        # Stored separately from capture-based extra turns.
        self._roll_grants_extra_turn: bool = False

        # Initialise 16 pawns and board occupancy
        self.pawns: dict[int, Pawn] = {}
        self.board: dict[tuple[int, int], list[int]] = {}
        self._init_pawns()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start_game(self) -> None:
        """Transition from WAITING to ROLLING.

        Must be the first action called on a new session.

        Raises:
            InvalidActionError: If the current state is not WAITING.
        """
        self._require_state(GameState.WAITING, "start_game")
        self._transition(GameState.ROLLING)
        self._emit_event("game_started", {"first_player": self.current_player_index})
        logger.info("Game started; first player: %d", self.current_player_index)

    def roll(self) -> RollResult:
        """Roll the cowrie shells and compute legal moves.

        Behaviour:
            * If legal moves exist → transition to SELECTING.
            * If no legal moves → advance the turn and stay in ROLLING.

        Returns:
            The :class:`~app.game.models.RollResult` for this throw.

        Raises:
            InvalidActionError: If the current state is not ROLLING.
        """
        self._require_state(GameState.ROLLING, "roll")

        result = roll_cowries(self._rng)
        self.current_roll = result
        self.roll_history.append(result)
        self._roll_grants_extra_turn = result.grants_extra_turn

        logger.debug(
            "Player %d rolled %d (extra_turn=%s)",
            self.current_player_index,
            result.value,
            result.grants_extra_turn,
        )

        self._emit_event(
            "roll",
            {
                "player_index": self.current_player_index,
                "value": result.value,
                "cowries": result.cowries,
                "grants_extra_turn": result.grants_extra_turn,
            },
        )

        self.legal_moves = self._compute_legal_moves(result.value)

        if self.legal_moves:
            self._transition(GameState.SELECTING)
            self._emit_event(
                "move_options",
                {
                    "player_index": self.current_player_index,
                    "pawn_ids": self.legal_moves,
                },
            )
        else:
            # No legal moves: turn passes regardless of roll value
            logger.debug(
                "Player %d has no legal moves; advancing turn",
                self.current_player_index,
            )
            self._emit_event(
                "no_moves",
                {"player_index": self.current_player_index, "roll": result.value},
            )
            self._advance_turn(extra_turn=False)

        return result

    def select_pawn(self, pawn_id: int) -> None:
        """Select a pawn to move with the current roll.

        Validates ownership and legality, executes the move, handles capture,
        checks win condition, then either grants an extra turn or advances to
        the next player.

        Args:
            pawn_id: The globally-unique pawn ID (0-15) to move.

        Raises:
            InvalidActionError: If the state is not SELECTING, the pawn does
                not belong to the current player, or the pawn is not in the
                legal-move list.
        """
        self._require_state(GameState.SELECTING, "select_pawn")

        if pawn_id not in self.pawns:
            raise InvalidActionError(
                f"Unknown pawn_id {pawn_id}; valid range is 0-15."
            )

        pawn = self.pawns[pawn_id]
        current_color = PlayerColor(self.current_player_index)
        if pawn.color != current_color:
            raise InvalidActionError(
                f"Pawn {pawn_id} belongs to player {pawn.color.name}, "
                f"but it is player {current_color.name}'s turn."
            )

        if pawn_id not in self.legal_moves:
            raise InvalidActionError(
                f"Pawn {pawn_id} is not in the current legal-move list "
                f"{self.legal_moves}."
            )

        # -- Move phase -------------------------------------------------
        self._transition(GameState.MOVING)
        prev_index = pawn.path_index
        new_index = self._compute_new_path_index(pawn)
        self._move_pawn(pawn, new_index)

        logger.debug(
            "Pawn %d moved: path_index %d → %d  pos=%s",
            pawn_id,
            prev_index,
            pawn.path_index,
            pawn.position,
        )
        self._emit_event(
            "pawn_moved",
            {
                "pawn_id": pawn_id,
                "from_index": prev_index,
                "to_index": pawn.path_index,
                "position": pawn.position,
            },
        )

        # -- Capture phase ----------------------------------------------
        captured_pawn_id: Optional[int] = self._find_capturable_enemy(pawn)
        capture_occurred = captured_pawn_id is not None

        if capture_occurred:
            self._transition(GameState.CAPTURING)
            assert captured_pawn_id is not None  # narrowing for mypy
            self._handle_capture(pawn, captured_pawn_id)

        # -- Win check --------------------------------------------------
        if self._is_current_player_winner():
            self._transition(GameState.GAME_OVER)
            self._emit_event(
                "game_over",
                {"winner_player_index": self.current_player_index},
            )
            logger.info(
                "Player %d wins!", self.current_player_index
            )
            return

        # -- Extra-turn / advance-turn decision -------------------------
        extra_turn = self._roll_grants_extra_turn or capture_occurred
        self._advance_turn(extra_turn=extra_turn)

    # ------------------------------------------------------------------
    # Private helpers – state transitions
    # ------------------------------------------------------------------

    def _transition(self, new_state: GameState) -> None:
        """Log and apply a state transition."""
        logger.debug(
            "FSM transition: %s → %s", self.state.name, new_state.name
        )
        self.state = new_state

    def _require_state(self, expected: GameState, action: str) -> None:
        """Raise InvalidActionError if the FSM is not in *expected* state."""
        if self.state != expected:
            raise InvalidActionError(
                f"Cannot call '{action}' in state {self.state.name}. "
                f"Expected: {expected.name}."
            )

    def _advance_turn(self, *, extra_turn: bool) -> None:
        """Move to ROLLING for the same player (extra turn) or next player."""
        if extra_turn:
            logger.debug(
                "Player %d receives an extra turn", self.current_player_index
            )
            self._emit_event(
                "extra_turn", {"player_index": self.current_player_index}
            )
        else:
            previous = self.current_player_index
            self.current_player_index = (
                self.current_player_index + 1
            ) % _NUM_PLAYERS
            self._emit_event(
                "turn_change",
                {
                    "from_player": previous,
                    "to_player": self.current_player_index,
                },
            )
            logger.debug(
                "Turn changed: player %d → player %d",
                previous,
                self.current_player_index,
            )

        # Reset per-turn transient state
        self.current_roll = None
        self.legal_moves = []
        self._roll_grants_extra_turn = False
        self._transition(GameState.ROLLING)

    # ------------------------------------------------------------------
    # Private helpers – move computation
    # ------------------------------------------------------------------

    def _compute_legal_moves(self, roll: int) -> list[int]:
        """Return pawn IDs that can legally move with *roll*.

        A pawn is legal when:
          1. It is not already at the win position.
          2. If in the home pen, the roll must be in PAWN_ENTRY_ROLLS {1, 8}.
          3. The computed new path index differs from the current path index
             (i.e., the pawn can actually move somewhere new).
          4. The destination is not blocked by a friendly pawn on a non-safe
             square.

        Returns:
            Sorted list of pawn IDs eligible to move.
        """
        current_color = PlayerColor(self.current_player_index)
        legal: list[int] = []

        for pawn in self._current_player_pawns():
            # Rule: pawn at win position cannot move further
            if pawn.path_index == WIN_TRACK_INDEX:
                continue

            # Rule: home pawn may only enter the board with roll 1 or 8
            if pawn.path_index == -1 and roll not in PAWN_ENTRY_ROLLS:
                continue

            new_idx = self._compute_new_path_index(pawn, override_roll=roll)

            # If new index equals current, the pawn cannot legally move
            if new_idx == pawn.path_index:
                continue

            new_pos = self._index_to_position(pawn.color, new_idx)

            # Rule: destination blocked by a friendly pawn on a non-safe square
            if not is_safe_square(new_pos) and self._has_friendly_at(
                new_pos, current_color, exclude_pawn_id=pawn.id
            ):
                continue

            legal.append(pawn.id)

        return sorted(legal)

    def _compute_new_path_index(
        self,
        pawn: Pawn,
        *,
        override_roll: Optional[int] = None,
    ) -> int:
        """Compute the new path_index for *pawn* using the current (or overridden) roll.

        Rules applied:
          * Home pen (path_index -1): new index = roll - 1 (equivalent to
            entering at track position ``roll``; only called for rolls in
            PAWN_ENTRY_ROLLS by ``_compute_legal_moves``).
          * Home-stretch restriction: if the player has not yet captured,
            the pawn may not advance into the home stretch (index ≥ 24).
          * Overshoot: if new index exceeds WIN_TRACK_INDEX (48) or the
            pawn is already at the win position, it stays put.

        Returns:
            The validated new path_index.  Returns the *current* path_index
            if the move is impossible (pawn stays in place).
        """
        roll = override_roll if override_roll is not None else (
            self.current_roll.value if self.current_roll else 0
        )
        k = pawn.path_index  # -1 or 0..48
        new_k = k + roll  # for home: -1 + roll = roll - 1

        has_captured = self._player_has_captured[pawn.color.value]

        # Home-stretch restriction: player must have captured before entering
        if new_k >= HOME_STRETCH_START and not has_captured:
            return k  # stay

        # Overshoot or already at win position
        if new_k > WIN_TRACK_INDEX or k == WIN_TRACK_INDEX:
            return k  # stay

        return new_k

    def _index_to_position(
        self, color: PlayerColor, path_index: int
    ) -> tuple[int, int]:
        """Return the board position for *color* at *path_index*.

        path_index == -1 returns the home-pen position.
        path_index 0..48 returns the track position.
        """
        if path_index == -1:
            return get_home_position(color.value)
        return get_track_position(color.value, path_index)

    # ------------------------------------------------------------------
    # Private helpers – board mutation
    # ------------------------------------------------------------------

    def _move_pawn(self, pawn: Pawn, new_path_index: int) -> None:
        """Update *pawn* position and the board occupancy dict."""
        old_pos = pawn.position
        new_pos = self._index_to_position(pawn.color, new_path_index)

        # Remove from old position
        if old_pos in self.board and pawn.id in self.board[old_pos]:
            self.board[old_pos].remove(pawn.id)
            if not self.board[old_pos]:
                del self.board[old_pos]

        # Update pawn state
        pawn.path_index = new_path_index
        pawn.position = new_pos

        # Add to new position
        self.board.setdefault(new_pos, []).append(pawn.id)

    def _find_capturable_enemy(self, pawn: Pawn) -> Optional[int]:
        """Return the ID of an enemy pawn that *pawn* can capture, or None.

        A capture occurs when *pawn* lands on a non-safe square occupied by
        an opponent's pawn.  Only one capture is performed per move (the
        legacy ``board_overview`` stored a single pawn per position).
        """
        pos = pawn.position
        if is_safe_square(pos):
            return None

        for occupant_id in list(self.board.get(pos, [])):
            if occupant_id == pawn.id:
                continue
            occupant = self.pawns[occupant_id]
            if occupant.color != pawn.color:
                return occupant_id  # first enemy found

        return None

    def _handle_capture(self, attacker: Pawn, victim_id: int) -> None:
        """Send *victim* back to its home pen and grant the current player a capture."""
        victim = self.pawns[victim_id]
        logger.debug(
            "Pawn %d (player %d) captures pawn %d (player %d)",
            attacker.id,
            attacker.color.value,
            victim_id,
            victim.color.value,
        )

        self._emit_event(
            "capture",
            {
                "capturing_pawn_id": attacker.id,
                "captured_pawn_id": victim_id,
                "position": attacker.position,
            },
        )

        # Send victim home
        self._move_pawn(victim, -1)

        # Record that the current player has now made a capture
        self._player_has_captured[attacker.color.value] = True

    # ------------------------------------------------------------------
    # Private helpers – win / query
    # ------------------------------------------------------------------

    def _is_current_player_winner(self) -> bool:
        """Return True if all 4 pawns of the current player are at the win position."""
        return all(
            p.path_index == WIN_TRACK_INDEX
            for p in self._current_player_pawns()
        )

    def _current_player_pawns(self) -> list[Pawn]:
        """Return the 4 Pawn objects belonging to the current player."""
        color = PlayerColor(self.current_player_index)
        return [p for p in self.pawns.values() if p.color == color]

    def _has_friendly_at(
        self,
        position: tuple[int, int],
        color: PlayerColor,
        *,
        exclude_pawn_id: int,
    ) -> bool:
        """Return True if a friendly pawn (other than *exclude_pawn_id*) is at *position*."""
        for pid in self.board.get(position, []):
            if pid == exclude_pawn_id:
                continue
            if self.pawns[pid].color == color:
                return True
        return False

    # ------------------------------------------------------------------
    # Private helpers – initialisation
    # ------------------------------------------------------------------

    def _init_pawns(self) -> None:
        """Create all 16 pawns at their home-pen positions."""
        for color_idx in range(_NUM_PLAYERS):
            color = PlayerColor(color_idx)
            home_pos = get_home_position(color_idx)
            for pawn_num in range(_PAWNS_PER_PLAYER):
                pid = _pawn_id(color_idx, pawn_num)
                pawn = Pawn(
                    id=pid,
                    color=color,
                    path_index=-1,
                    position=home_pos,
                )
                self.pawns[pid] = pawn
                self.board.setdefault(home_pos, []).append(pid)

    # ------------------------------------------------------------------
    # Private helpers – event emission
    # ------------------------------------------------------------------

    def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Append a typed event dict to ``self.events``."""
        self.events.append({"type": event_type, **data})

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"GameSession(state={self.state.name}, "
            f"player={self.current_player_index}, "
            f"roll={self.current_roll.value if self.current_roll else None})"
        )
