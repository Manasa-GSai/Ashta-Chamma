"""Tests for the game state machine (app.game.state_machine).

Acceptance criteria covered:
  AC6  — State transitions: WAITING→ROLLING→SELECTING→MOVING→ROLLING/GAME_OVER.
  AC8  — Extra turn granted on roll of 1/4/8 and on capture.
  AC11 — Invalid action rejection (wrong player, wrong state).
"""

from __future__ import annotations

import pytest

from app.game.board import PATHS, SAFE_SQUARES, WIN_PATH_INDEX
from app.game.dice import make_roll
from app.game.state_machine import GameError, GameSession, GameState, MoveResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def session() -> GameSession:
    return GameSession(session_id="sm-test")


# ---------------------------------------------------------------------------
# AC6 — State transitions
# ---------------------------------------------------------------------------


class TestStateTransitions:
    """Full WAITING→ROLLING→SELECTING→MOVING→ROLLING/GAME_OVER flow."""

    def test_initial_state_is_waiting(self, session: GameSession) -> None:
        assert session.state == GameState.WAITING

    def test_start_game_transitions_to_rolling(self, session: GameSession) -> None:
        session.start_game()
        assert session.state == GameState.ROLLING

    def test_apply_roll_with_moves_transitions_to_selecting(
        self, session: GameSession
    ) -> None:
        session.start_game()
        # Roll 1 allows release — so legal moves exist.
        session.apply_roll(make_roll(1))
        assert session.state == GameState.SELECTING

    def test_apply_move_transitions_to_moving(self, session: GameSession) -> None:
        session.start_game()
        session.apply_roll(make_roll(1))
        session.apply_move(player_index=0, pawn_index=0)
        assert session.state == GameState.MOVING

    def test_confirm_move_transitions_to_rolling_on_extra_turn(
        self, session: GameSession
    ) -> None:
        """Roll 1 grants extra turn — after confirm_move, state is ROLLING for same player."""
        session.start_game()
        session.apply_roll(make_roll(1))
        session.apply_move(player_index=0, pawn_index=0)
        session.confirm_move()
        assert session.state == GameState.ROLLING
        assert session.current_player == 0  # same player rolls again

    def test_confirm_move_advances_turn_on_no_extra_turn(
        self, session: GameSession
    ) -> None:
        """Roll 2 gives no extra turn — after confirm_move, turn passes to player 1."""
        session.start_game()
        # Advance pawn to path index 1 first (it's in play), then roll 2.
        session.pawn_positions[0][0] = 1
        session.apply_roll(make_roll(2))
        session.apply_move(player_index=0, pawn_index=0)
        session.confirm_move()
        assert session.state == GameState.ROLLING
        assert session.current_player == 1

    def test_roll_with_no_moves_advances_turn(self, session: GameSession) -> None:
        """Roll 2 when all pawns are home yields no moves — turn advances automatically."""
        session.start_game()
        # All pawns home; roll 2 cannot release.
        session.apply_roll(make_roll(2))
        assert session.state == GameState.ROLLING
        assert session.current_player == 1

    def test_full_turn_cycle_four_players(self, session: GameSession) -> None:
        """Passing turns through all four players wraps back to player 0."""
        session.start_game()
        for expected_player in range(4):
            assert session.current_player == expected_player
            session.apply_roll(make_roll(2))  # no pawns in play → auto-advance
        assert session.current_player == 0

    def test_game_over_state_reached_on_win(self, session: GameSession) -> None:
        """State transitions to GAME_OVER when the last pawn reaches centre."""
        session.start_game()
        # Place three of player 0's pawns already at WIN_PATH_INDEX.
        session.pawn_positions[0] = [WIN_PATH_INDEX, WIN_PATH_INDEX, WIN_PATH_INDEX, 47]
        # Roll 2 advances pawn 3 from index 47 to WIN_PATH_INDEX.
        session.apply_roll(make_roll(2))
        session.apply_move(player_index=0, pawn_index=3)
        session.confirm_move()
        assert session.state == GameState.GAME_OVER
        assert session.winner == 0


# ---------------------------------------------------------------------------
# AC8 — Extra turn rules
# ---------------------------------------------------------------------------


class TestExtraTurnRules:
    """Extra turn is granted after rolling 1, 4, or 8, or after a capture."""

    @pytest.mark.parametrize("roll_value", [1, 4, 8])
    def test_extra_turn_on_roll_1_4_8(
        self, session: GameSession, roll_value: int
    ) -> None:
        """AC8: Rolls 1, 4, 8 grant extra turn to same player."""
        session.start_game()
        # Put pawn 0 in play at a position where all three roll values work.
        session.pawn_positions[0][0] = 10
        session.apply_roll(make_roll(roll_value))
        result = session.apply_move(player_index=0, pawn_index=0)
        assert result.extra_turn is True
        session.confirm_move()
        assert session.current_player == 0  # still player 0's turn

    def test_no_extra_turn_on_roll_2(self, session: GameSession) -> None:
        """AC8: Roll 2 must NOT grant extra turn."""
        session.start_game()
        session.pawn_positions[0][0] = 10
        session.apply_roll(make_roll(2))
        result = session.apply_move(player_index=0, pawn_index=0)
        assert result.extra_turn is False
        session.confirm_move()
        assert session.current_player == 1

    def test_no_extra_turn_on_roll_3(self, session: GameSession) -> None:
        """AC8: Roll 3 must NOT grant extra turn."""
        session.start_game()
        session.pawn_positions[0][0] = 10
        session.apply_roll(make_roll(3))
        result = session.apply_move(player_index=0, pawn_index=0)
        assert result.extra_turn is False

    def test_extra_turn_on_capture(self, session: GameSession) -> None:
        """AC8: Capturing an opponent pawn grants an extra turn.

        Setup: player 0's pawn 0 is at path index 4 (non-safe square area).
        After rolling 1 it moves to index 5.  We place player 1's pawn on
        the same physical square so a capture occurs.
        """
        session.start_game()

        p0_from = 4
        p0_to = p0_from + 1  # roll 1

        # Make sure the target square is not safe; scan forward if needed.
        while PATHS[0][p0_to] in SAFE_SQUARES and p0_to < 20:
            p0_from += 1
            p0_to = p0_from + 1

        target_sq = PATHS[0][p0_to]
        if target_sq in SAFE_SQUARES:
            pytest.skip("Could not find a non-safe target square in range")

        # Find player 1's path index that maps to the same physical square.
        p1_index: int | None = None
        for i, sq in enumerate(PATHS[1]):
            if sq == target_sq and i not in (0, WIN_PATH_INDEX):
                p1_index = i
                break

        if p1_index is None:
            pytest.skip("Player 1's path does not cross the chosen target square")

        session.pawn_positions[0][0] = p0_from
        session.pawn_positions[1][0] = p1_index

        session.apply_roll(make_roll(1))
        result = session.apply_move(player_index=0, pawn_index=0)

        assert result.captured is True, "Expected a capture to occur"
        assert result.extra_turn is True, "Capture should grant extra turn"
        assert session.pawn_positions[1][0] == 0, "Captured pawn should return home"

    def test_no_capture_on_safe_square(self, session: GameSession) -> None:
        """AC7/AC8: Landing on a safe square does not capture opponent pawn."""
        session.start_game()

        # PATHS[0][1] == (1,4) which is a safe square; reach it with roll 1 from home.
        safe_idx = 1
        safe_sq = PATHS[0][safe_idx]
        assert safe_sq in SAFE_SQUARES

        # Find player 1's path index for the same physical safe square.
        p1_index: int | None = None
        for i, sq in enumerate(PATHS[1]):
            if sq == safe_sq and i not in (0, WIN_PATH_INDEX):
                p1_index = i
                break

        if p1_index is None:
            pytest.skip("Player 1 path does not cross (1,4)")

        session.pawn_positions[1][0] = p1_index

        # Player 0 pawn at home, roll 1 → lands on safe square.
        session.apply_roll(make_roll(1))
        result = session.apply_move(player_index=0, pawn_index=0)

        assert result.captured is False
        # Player 1's pawn must remain in place.
        assert session.pawn_positions[1][0] == p1_index


# ---------------------------------------------------------------------------
# AC11 — Invalid action rejection
# ---------------------------------------------------------------------------


class TestInvalidActionRejection:
    """GameError is raised for illegal actions."""

    def test_start_game_wrong_state_raises(self, session: GameSession) -> None:
        session.start_game()
        with pytest.raises(GameError, match="WAITING"):
            session.start_game()

    def test_roll_before_start_raises(self, session: GameSession) -> None:
        with pytest.raises(GameError):
            session.apply_roll(make_roll(1))

    def test_roll_wrong_player_raises(self, session: GameSession) -> None:
        session.start_game()
        with pytest.raises(GameError, match="player"):
            session.apply_roll(make_roll(1), player_index=1)

    def test_move_before_roll_raises(self, session: GameSession) -> None:
        session.start_game()
        with pytest.raises(GameError):
            session.apply_move(player_index=0, pawn_index=0)

    def test_move_wrong_player_raises(self, session: GameSession) -> None:
        session.start_game()
        session.apply_roll(make_roll(1))
        with pytest.raises(GameError, match="player"):
            session.apply_move(player_index=1, pawn_index=0)

    def test_move_invalid_pawn_raises(self, session: GameSession) -> None:
        session.start_game()
        session.apply_roll(make_roll(1))
        # Pawn 99 has no legal move.
        with pytest.raises(GameError):
            session.apply_move(player_index=0, pawn_index=99)

    def test_confirm_move_wrong_state_raises(self, session: GameSession) -> None:
        session.start_game()
        with pytest.raises(GameError):
            session.confirm_move()

    def test_action_in_game_over_state_raises(self, session: GameSession) -> None:
        """Once game is over, rolling is rejected."""
        session.start_game()
        session.pawn_positions[0] = [WIN_PATH_INDEX, WIN_PATH_INDEX, WIN_PATH_INDEX, 47]
        session.apply_roll(make_roll(2))
        session.apply_move(player_index=0, pawn_index=3)
        session.confirm_move()
        assert session.state == GameState.GAME_OVER
        with pytest.raises(GameError):
            session.apply_roll(make_roll(1))

    def test_selecting_then_roll_raises(self, session: GameSession) -> None:
        """Cannot roll again while in SELECTING state."""
        session.start_game()
        session.apply_roll(make_roll(1))
        assert session.state == GameState.SELECTING
        with pytest.raises(GameError):
            session.apply_roll(make_roll(1))


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------


class TestSessionMetadata:
    def test_session_id_stored(self, session: GameSession) -> None:
        assert session.session_id == "sm-test"

    def test_initial_current_player_is_zero(self, session: GameSession) -> None:
        assert session.current_player == 0

    def test_initial_winner_is_none(self, session: GameSession) -> None:
        assert session.winner is None

    def test_last_roll_updated_after_roll(self, session: GameSession) -> None:
        session.start_game()
        session.apply_roll(make_roll(3))
        assert session.last_roll == 3

    def test_legal_moves_cleared_after_move(self, session: GameSession) -> None:
        session.start_game()
        session.apply_roll(make_roll(1))
        assert len(session.legal_moves) > 0
        session.apply_move(player_index=0, pawn_index=0)
        assert session.legal_moves == []
