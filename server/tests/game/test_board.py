"""Tests for board topology constants (app.game.board).

Acceptance criteria covered:
  AC4 — All 4 player paths end at (4,4).
  AC4 — Safe squares are correct.
  AC4 — Home positions are correct.
"""

from __future__ import annotations

import pytest

from app.game.board import (
    CENTER,
    HOME_POSITIONS,
    HOME_STRETCH_START,
    NUM_PLAYERS,
    PATH_LENGTH,
    PATHS,
    PAWNS_PER_PLAYER,
    SAFE_SQUARES,
    WIN_PATH_INDEX,
)


# ---------------------------------------------------------------------------
# Path structure
# ---------------------------------------------------------------------------


class TestPathStructure:
    """All four player paths must satisfy structural invariants."""

    @pytest.mark.parametrize("player", [0, 1, 2, 3])
    def test_path_has_correct_length(self, player: int) -> None:
        assert len(PATHS[player]) == PATH_LENGTH, (
            f"Player {player} path has {len(PATHS[player])} entries; expected {PATH_LENGTH}"
        )

    @pytest.mark.parametrize("player", [0, 1, 2, 3])
    def test_path_ends_at_centre(self, player: int) -> None:
        """AC4: All 4 player paths end at (4,4)."""
        assert PATHS[player][WIN_PATH_INDEX] == CENTER, (
            f"Player {player} path does not end at {CENTER}; "
            f"got {PATHS[player][WIN_PATH_INDEX]}"
        )

    @pytest.mark.parametrize("player", [0, 1, 2, 3])
    def test_path_starts_at_home(self, player: int) -> None:
        """Index 0 of each path must be the player's home base."""
        assert PATHS[player][0] == HOME_POSITIONS[player], (
            f"Player {player} path index 0 is {PATHS[player][0]}; "
            f"expected home position {HOME_POSITIONS[player]}"
        )

    @pytest.mark.parametrize("player", [0, 1, 2, 3])
    def test_path_indices_are_unique(self, player: int) -> None:
        """Each square on a player's path should appear at most once."""
        path = PATHS[player]
        assert len(set(path)) == len(path), (
            f"Player {player} path contains duplicate squares"
        )

    def test_num_players(self) -> None:
        assert NUM_PLAYERS == 4

    def test_pawns_per_player(self) -> None:
        assert PAWNS_PER_PLAYER == 4

    def test_win_path_index_is_last(self) -> None:
        assert WIN_PATH_INDEX == PATH_LENGTH - 1

    def test_home_stretch_start(self) -> None:
        assert HOME_STRETCH_START == 25


# ---------------------------------------------------------------------------
# Safe squares
# ---------------------------------------------------------------------------


class TestSafeSquares:
    """AC4: Safe squares are correct."""

    EXPECTED_SAFE: frozenset[tuple[int, int]] = frozenset(
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

    def test_safe_squares_match_expected(self) -> None:
        assert SAFE_SQUARES == self.EXPECTED_SAFE

    def test_centre_is_safe(self) -> None:
        """The winning centre square must be safe (pawns can't be captured there)."""
        assert CENTER in SAFE_SQUARES

    @pytest.mark.parametrize(
        "sq",
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
        ],
    )
    def test_known_safe_square_present(self, sq: tuple[int, int]) -> None:
        assert sq in SAFE_SQUARES

    def test_non_safe_square_absent(self) -> None:
        assert (3, 3) not in SAFE_SQUARES
        assert (5, 5) not in SAFE_SQUARES
        assert (1, 1) not in SAFE_SQUARES

    def test_safe_squares_count(self) -> None:
        assert len(SAFE_SQUARES) == 9


# ---------------------------------------------------------------------------
# Home positions
# ---------------------------------------------------------------------------


class TestHomePositions:
    """AC4: Home positions are correct."""

    EXPECTED: tuple[tuple[int, int], ...] = (
        (0, 4),
        (4, 0),
        (8, 4),
        (4, 8),
    )

    def test_home_positions_match_expected(self) -> None:
        assert HOME_POSITIONS == self.EXPECTED

    @pytest.mark.parametrize(
        "player,expected_home",
        [
            (0, (0, 4)),
            (1, (4, 0)),
            (2, (8, 4)),
            (3, (4, 8)),
        ],
    )
    def test_individual_home_positions(
        self, player: int, expected_home: tuple[int, int]
    ) -> None:
        assert HOME_POSITIONS[player] == expected_home

    def test_home_positions_are_distinct(self) -> None:
        assert len(set(HOME_POSITIONS)) == NUM_PLAYERS

    def test_home_positions_not_on_board_inner(self) -> None:
        """Home bases are on the outer edge of the 9×9 grid."""
        for hp in HOME_POSITIONS:
            row, col = hp
            # At least one coordinate must be 0 or 8 (outer edge).
            assert row in (0, 8) or col in (0, 8), (
                f"Home position {hp} is not on the outer edge"
            )


# ---------------------------------------------------------------------------
# Centre constant
# ---------------------------------------------------------------------------


class TestCenter:
    def test_centre_value(self) -> None:
        assert CENTER == (4, 4)

    @pytest.mark.parametrize("player", [0, 1, 2, 3])
    def test_all_paths_reach_centre(self, player: int) -> None:
        assert CENTER in PATHS[player]
