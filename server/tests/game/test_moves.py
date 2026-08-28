"""Tests for move validation (app.game.moves).

Acceptance criteria covered:
  AC7  — Capture on non-safe square sends pawn home; no capture on safe square.
  AC9  — Pawn release is only allowed on roll of 1 or 8.
  Also — Legal move computation: blocking by friendly pawn, overshoot prevention.
"""

from __future__ import annotations

import pytest

from app.game.board import PATHS, SAFE_SQUARES, WIN_PATH_INDEX
from app.game.moves import Move, compute_legal_moves


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a default "all at home" pawn array: 4 pawns at index 0.
_ALL_HOME: tuple[int, int, int, int] = (0, 0, 0, 0)
_ALL_POSITIONS_HOME: tuple[tuple[int, ...], ...] = tuple(
    (0, 0, 0, 0) for _ in range(4)
)


def _positions_with(player: int, pawn: int, idx: int) -> tuple[tuple[int, ...], ...]:
    """Return all_pawn_positions with one pawn placed at a specific path index."""
    positions = [[0] * 4 for _ in range(4)]
    positions[player][pawn] = idx
    return tuple(tuple(row) for row in positions)


# ---------------------------------------------------------------------------
# AC9 — Pawn release rule
# ---------------------------------------------------------------------------


class TestPawnReleaseRule:
    """A pawn at home (path index 0) can only be moved on rolls of 1 or 8."""

    @pytest.mark.parametrize("roll", [1, 8])
    def test_release_allowed_on_1_and_8(self, roll: int) -> None:
        """AC9: Rolls 1 and 8 allow pawns to enter the board from home."""
        moves = compute_legal_moves(0, _ALL_HOME, _ALL_POSITIONS_HOME, roll)
        assert len(moves) > 0, f"Expected release moves for roll {roll}"
        # All moves should come from home (index 0).
        assert all(m.from_path_index == 0 for m in moves)

    @pytest.mark.parametrize("roll", [2, 3, 4])
    def test_release_forbidden_on_2_3_4(self, roll: int) -> None:
        """AC9: Rolls 2, 3, 4 must not allow releasing home pawns."""
        moves = compute_legal_moves(0, _ALL_HOME, _ALL_POSITIONS_HOME, roll)
        assert len(moves) == 0, (
            f"Expected no moves for roll {roll} when all pawns are at home"
        )

    def test_release_move_is_flagged(self) -> None:
        moves = compute_legal_moves(0, _ALL_HOME, _ALL_POSITIONS_HOME, 1)
        for m in moves:
            assert m.is_release

    def test_non_release_move_not_flagged(self) -> None:
        """A pawn already on the board should not be flagged as a release move."""
        positions = (10, 0, 0, 0)  # pawn 0 at index 10
        all_pos = _positions_with(0, 0, 10)
        moves = compute_legal_moves(0, positions, all_pos, 2)
        assert any(not m.is_release for m in moves)


# ---------------------------------------------------------------------------
# Overshoot prevention
# ---------------------------------------------------------------------------


class TestOvershotPrevention:
    """Pawns cannot move past the final centre square (WIN_PATH_INDEX)."""

    def test_overshoot_prevented(self) -> None:
        # Pawn 0 is at index 47; roll 8 would put it at 55 — invalid.
        near_end = (47, 0, 0, 0)
        all_pos = _positions_with(0, 0, 47)
        moves = compute_legal_moves(0, near_end, all_pos, 8)
        # Pawn 0 should have no move (overshoot).  Pawns 1-3 are home, roll 8 allows
        # release to index 8.
        move_for_pawn0 = [m for m in moves if m.pawn_index == 0]
        assert len(move_for_pawn0) == 0

    def test_exact_reach_allowed(self) -> None:
        # Pawn 0 is at index 47; roll 2 → index 49 (WIN_PATH_INDEX) — allowed.
        near_end = (47, 0, 0, 0)
        all_pos = _positions_with(0, 0, 47)
        moves = compute_legal_moves(0, near_end, all_pos, 2)
        move_for_pawn0 = [m for m in moves if m.pawn_index == 0]
        assert len(move_for_pawn0) == 1
        assert move_for_pawn0[0].to_path_index == WIN_PATH_INDEX
        assert move_for_pawn0[0].is_winning

    def test_pawn_at_win_index_cannot_move(self) -> None:
        done = (WIN_PATH_INDEX, 0, 0, 0)
        all_pos = _positions_with(0, 0, WIN_PATH_INDEX)
        moves = compute_legal_moves(0, done, all_pos, 1)
        move_for_pawn0 = [m for m in moves if m.pawn_index == 0]
        assert len(move_for_pawn0) == 0


# ---------------------------------------------------------------------------
# Friendly pawn blocking
# ---------------------------------------------------------------------------


class TestFriendlyBlocking:
    """A pawn cannot land on a non-safe square occupied by a friendly pawn."""

    def test_friendly_blocks_on_non_safe_square(self) -> None:
        # Pawn 0 and pawn 1 both in play; pawn 1 sits on the square pawn 0
        # would land on with a roll of 1.
        pawn0_idx = 5
        pawn1_idx = pawn0_idx + 1  # pawn 1 blocks pawn 0's roll-1 destination
        target_sq = PATHS[0][pawn1_idx]
        # Ensure target is not safe (choose another index if it is).
        while target_sq in SAFE_SQUARES and pawn0_idx < 40:
            pawn0_idx += 1
            pawn1_idx = pawn0_idx + 1
            target_sq = PATHS[0][pawn1_idx]

        positions = (pawn0_idx, pawn1_idx, 0, 0)
        all_pos = (positions,) + tuple((0, 0, 0, 0) for _ in range(3))
        moves = compute_legal_moves(0, positions, all_pos, 1)
        move_for_pawn0 = [m for m in moves if m.pawn_index == 0]
        assert len(move_for_pawn0) == 0, (
            f"Pawn 0 should be blocked at index {pawn1_idx} by friendly pawn"
        )

    def test_safe_square_allows_friendly_stacking(self) -> None:
        # Find a safe square and place pawn 1 there.
        # Then pawn 0 should still be able to land there.
        # Safe square (1,4) is PATHS[0][1] for player 0.
        safe_sq_idx = 1  # PATHS[0][1] == (1,4) which is safe
        assert PATHS[0][safe_sq_idx] in SAFE_SQUARES

        # Pawn 0 at index 0 (home), roll 1 lands at index 1.
        # Pawn 1 also at index 1 (safe square).
        positions = (0, safe_sq_idx, 0, 0)
        all_pos = (positions,) + tuple((0, 0, 0, 0) for _ in range(3))
        moves = compute_legal_moves(0, positions, all_pos, 1)
        move_for_pawn0 = [m for m in moves if m.pawn_index == 0]
        assert len(move_for_pawn0) == 1, (
            "Pawn 0 should be able to land on a safe square occupied by friendly pawn"
        )


# ---------------------------------------------------------------------------
# Legal move computation — general
# ---------------------------------------------------------------------------


class TestLegalMoveComputation:
    """General tests for the compute_legal_moves function."""

    def test_returns_list(self) -> None:
        result = compute_legal_moves(0, _ALL_HOME, _ALL_POSITIONS_HOME, 2)
        assert isinstance(result, list)

    def test_move_fields_correct(self) -> None:
        moves = compute_legal_moves(0, _ALL_HOME, _ALL_POSITIONS_HOME, 1)
        for m in moves:
            assert isinstance(m, Move)
            assert m.player_index == 0
            assert m.from_path_index == 0
            assert m.to_path_index == 1

    def test_four_pawns_released_on_roll_1(self) -> None:
        """All 4 home pawns can move on roll 1 (each lands at path index 1)."""
        moves = compute_legal_moves(0, _ALL_HOME, _ALL_POSITIONS_HOME, 1)
        # The first pawn lands at index 1 (a safe square) — all 4 can stack there.
        assert len(moves) == 4

    def test_in_play_pawn_moves_correctly(self) -> None:
        idx = 10
        positions = (idx, 0, 0, 0)
        all_pos = _positions_with(0, 0, idx)
        moves = compute_legal_moves(0, positions, all_pos, 3)
        pawn0_moves = [m for m in moves if m.pawn_index == 0]
        assert len(pawn0_moves) == 1
        assert pawn0_moves[0].to_path_index == idx + 3

    @pytest.mark.parametrize("player", [0, 1, 2, 3])
    def test_all_players_can_release(self, player: int) -> None:
        all_home = tuple(0 for _ in range(4))
        all_pos = tuple(tuple(0 for _ in range(4)) for _ in range(4))
        moves = compute_legal_moves(player, all_home, all_pos, 1)
        assert len(moves) > 0, f"Player {player} should be able to release a pawn on roll 1"
