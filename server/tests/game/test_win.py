"""Tests for win condition detection (app.game.state_machine + app.game.moves).

Acceptance criteria covered:
  AC10 — Win condition when all 4 pawns reach the centre square.
"""

from __future__ import annotations

import pytest

from app.game.board import WIN_PATH_INDEX
from app.game.dice import make_roll
from app.game.state_machine import GameError, GameSession, GameState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _place_player_near_win(session: GameSession, player: int, last_pawn_idx: int) -> None:
    """Put first three pawns at WIN_PATH_INDEX and last pawn at *last_pawn_idx*."""
    session.pawn_positions[player] = [
        WIN_PATH_INDEX,
        WIN_PATH_INDEX,
        WIN_PATH_INDEX,
        last_pawn_idx,
    ]


# ---------------------------------------------------------------------------
# AC10 — Win condition
# ---------------------------------------------------------------------------


class TestWinCondition:
    """Win is detected when all 4 pawns of one player reach the centre."""

    def test_win_detected_when_last_pawn_reaches_centre(self) -> None:
        """AC10: Game ends with correct winner when 4th pawn reaches (4,4)."""
        session = GameSession(session_id="win-test-1")
        session.start_game()
        _place_player_near_win(session, player=0, last_pawn_idx=47)
        # Roll 2: pawn 3 moves from 47 → 49 (WIN_PATH_INDEX).
        session.apply_roll(make_roll(2))
        result = session.apply_move(player_index=0, pawn_index=3)
        assert result.winner == 0
        session.confirm_move()
        assert session.state == GameState.GAME_OVER
        assert session.winner == 0

    def test_win_not_detected_prematurely(self) -> None:
        """Three pawns at centre is not a win."""
        session = GameSession(session_id="win-test-2")
        session.start_game()
        session.pawn_positions[0] = [WIN_PATH_INDEX, WIN_PATH_INDEX, WIN_PATH_INDEX, 10]
        session.apply_roll(make_roll(1))
        result = session.apply_move(player_index=0, pawn_index=3)
        assert result.winner is None
        session.confirm_move()
        # Game should NOT be over.
        assert session.state != GameState.GAME_OVER

    @pytest.mark.parametrize("roll_to_win", [1, 2])
    def test_win_via_different_final_rolls(self, roll_to_win: int) -> None:
        """Win is detected regardless of the final roll value."""
        session = GameSession(session_id=f"win-roll-{roll_to_win}")
        session.start_game()
        last_idx = WIN_PATH_INDEX - roll_to_win
        _place_player_near_win(session, player=0, last_pawn_idx=last_idx)
        session.apply_roll(make_roll(roll_to_win))
        result = session.apply_move(player_index=0, pawn_index=3)
        assert result.winner == 0
        session.confirm_move()
        assert session.state == GameState.GAME_OVER

    @pytest.mark.parametrize("winning_player", [0, 1, 2, 3])
    def test_any_player_can_win(self, winning_player: int) -> None:
        """Any of the four players can trigger a win."""
        session = GameSession(session_id=f"win-player-{winning_player}")
        session.start_game()

        # Advance all players' turns until it is winning_player's turn.
        for _ in range(winning_player):
            session.apply_roll(make_roll(2))  # no pawns home → no moves → auto-advance

        assert session.current_player == winning_player

        # Set up near-win state for this player.
        _place_player_near_win(session, player=winning_player, last_pawn_idx=47)
        session.apply_roll(make_roll(2))
        result = session.apply_move(player_index=winning_player, pawn_index=3)
        assert result.winner == winning_player
        session.confirm_move()
        assert session.winner == winning_player
        assert session.state == GameState.GAME_OVER

    def test_winner_stored_on_session(self) -> None:
        """The winner attribute is populated and then read-only in GAME_OVER."""
        session = GameSession(session_id="win-store")
        session.start_game()
        _place_player_near_win(session, player=0, last_pawn_idx=48)
        session.apply_roll(make_roll(1))
        session.apply_move(player_index=0, pawn_index=3)
        session.confirm_move()
        assert session.winner == 0

    def test_pawn_at_win_index_is_done(self) -> None:
        """A pawn at WIN_PATH_INDEX should not appear in legal moves."""
        from app.game.moves import compute_legal_moves

        positions = (WIN_PATH_INDEX, WIN_PATH_INDEX, WIN_PATH_INDEX, WIN_PATH_INDEX)
        all_pos = (positions,) + tuple((0, 0, 0, 0) for _ in range(3))
        moves = compute_legal_moves(0, positions, all_pos, 1)
        assert moves == [], "No moves should exist when all pawns have won"

    def test_single_pawn_at_win_index_ignored(self) -> None:
        """Pawn already at centre is skipped in move computation."""
        from app.game.moves import compute_legal_moves

        positions = (WIN_PATH_INDEX, 0, 0, 0)
        all_pos = (positions,) + tuple((0, 0, 0, 0) for _ in range(3))
        moves = compute_legal_moves(0, positions, all_pos, 1)
        # Pawns 1-3 are at home and roll 1 releases them; pawn 0 is done.
        assert all(m.pawn_index != 0 for m in moves)

    def test_game_over_blocks_further_rolls(self) -> None:
        """After GAME_OVER, any call to apply_roll raises GameError."""
        session = GameSession(session_id="win-block")
        session.start_game()
        _place_player_near_win(session, player=0, last_pawn_idx=47)
        session.apply_roll(make_roll(2))
        session.apply_move(player_index=0, pawn_index=3)
        session.confirm_move()
        assert session.state == GameState.GAME_OVER
        with pytest.raises(GameError):
            session.apply_roll(make_roll(1))

    def test_all_pawns_check_private_method(self) -> None:
        """_check_win returns False when not all pawns are done."""
        session = GameSession(session_id="check-win")
        session.pawn_positions[0] = [WIN_PATH_INDEX, WIN_PATH_INDEX, 5, WIN_PATH_INDEX]
        assert session._check_win(0) is False
        session.pawn_positions[0][2] = WIN_PATH_INDEX
        assert session._check_win(0) is True
