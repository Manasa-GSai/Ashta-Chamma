"""Unit tests for server/app/game/board.py.

Covers:
- All paths end at the center square (4, 4)
- No out-of-bounds coordinates in any path
- No duplicate coordinates within any path
- Path lengths are exactly 50
- Safe squares match the expected frozenset
- Home positions match expected values per player
- validate_paths() raises ValueError when data is corrupted
- PlayerColor enum values match legacy index ordering
- CENTER constant is correct
"""

import copy

import pytest

from app.game.board import (
    CENTER,
    HOME_POSITIONS,
    PATHS,
    SAFE_SQUARES,
    PlayerColor,
    validate_paths,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALL_PLAYERS = list(PlayerColor)
_GRID_MIN = 0
_GRID_MAX = 8
_EXPECTED_LENGTH = 50


# ---------------------------------------------------------------------------
# PlayerColor enum
# ---------------------------------------------------------------------------


def test_player_color_values_match_legacy_ordering() -> None:
    """Legacy code uses R=0, B=1, G=2, Y=3."""
    assert PlayerColor.RED == 0
    assert PlayerColor.BLUE == 1
    assert PlayerColor.GREEN == 2
    assert PlayerColor.YELLOW == 3


def test_player_color_has_four_members() -> None:
    assert len(PlayerColor) == 4


# ---------------------------------------------------------------------------
# CENTER constant
# ---------------------------------------------------------------------------


def test_center_is_correct() -> None:
    assert CENTER == (4, 4)


# ---------------------------------------------------------------------------
# Path length
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("color", _ALL_PLAYERS)
def test_path_length(color: PlayerColor) -> None:
    assert len(PATHS[color]) == _EXPECTED_LENGTH, (
        f"Path for {color.name} has {len(PATHS[color])} steps, expected {_EXPECTED_LENGTH}"
    )


# ---------------------------------------------------------------------------
# All paths end at CENTER
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("color", _ALL_PLAYERS)
def test_path_ends_at_center(color: PlayerColor) -> None:
    last = PATHS[color][-1]
    assert last == CENTER, (
        f"Path for {color.name} ends at {last}, expected {CENTER}"
    )


# ---------------------------------------------------------------------------
# No out-of-bounds coordinates
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("color", _ALL_PLAYERS)
def test_all_coordinates_within_bounds(color: PlayerColor) -> None:
    for step, (row, col) in enumerate(PATHS[color]):
        assert _GRID_MIN <= row <= _GRID_MAX, (
            f"Path for {color.name}, step {step}: row {row} out of range"
        )
        assert _GRID_MIN <= col <= _GRID_MAX, (
            f"Path for {color.name}, step {step}: col {col} out of range"
        )


# ---------------------------------------------------------------------------
# No duplicate coordinates per path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("color", _ALL_PLAYERS)
def test_no_duplicate_coordinates(color: PlayerColor) -> None:
    path = PATHS[color]
    seen: set[tuple[int, int]] = set()
    duplicates: list[tuple[int, int]] = []
    for coord in path:
        if coord in seen:
            duplicates.append(coord)
        seen.add(coord)
    assert duplicates == [], (
        f"Path for {color.name} contains duplicates: {duplicates}"
    )


# ---------------------------------------------------------------------------
# Safe squares
# ---------------------------------------------------------------------------


def test_safe_squares_exact_set() -> None:
    expected: frozenset[tuple[int, int]] = frozenset(
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
    assert SAFE_SQUARES == expected


def test_safe_squares_count() -> None:
    assert len(SAFE_SQUARES) == 9


def test_safe_squares_is_frozenset() -> None:
    assert isinstance(SAFE_SQUARES, frozenset)


def test_center_is_in_safe_squares() -> None:
    assert CENTER in SAFE_SQUARES


# ---------------------------------------------------------------------------
# Home positions
# ---------------------------------------------------------------------------


def test_home_positions_red() -> None:
    assert HOME_POSITIONS[PlayerColor.RED] == (0, 4)


def test_home_positions_blue() -> None:
    assert HOME_POSITIONS[PlayerColor.BLUE] == (4, 0)


def test_home_positions_green() -> None:
    assert HOME_POSITIONS[PlayerColor.GREEN] == (8, 4)


def test_home_positions_yellow() -> None:
    assert HOME_POSITIONS[PlayerColor.YELLOW] == (4, 8)


def test_home_positions_all_players_defined() -> None:
    for color in PlayerColor:
        assert color in HOME_POSITIONS, f"HOME_POSITIONS missing key for {color.name}"


def test_home_positions_match_path_start() -> None:
    """Each home position must equal the first coordinate in that player's path."""
    for color in PlayerColor:
        assert HOME_POSITIONS[color] == PATHS[color][0], (
            f"HOME_POSITIONS[{color.name}] = {HOME_POSITIONS[color]} "
            f"but PATHS[{color.name}][0] = {PATHS[color][0]}"
        )


# ---------------------------------------------------------------------------
# validate_paths() — happy path
# ---------------------------------------------------------------------------


def test_validate_paths_passes_on_valid_data() -> None:
    """No exception should be raised when PATHS is intact."""
    validate_paths()


# ---------------------------------------------------------------------------
# validate_paths() — error cases
# ---------------------------------------------------------------------------


def test_validate_paths_raises_on_wrong_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """Truncating a path should raise ValueError."""
    patched = {color: list(path) for color, path in PATHS.items()}
    patched[PlayerColor.RED] = patched[PlayerColor.RED][:-1]  # remove last step
    monkeypatch.setattr("app.game.board.PATHS", patched)
    with pytest.raises(ValueError, match="steps"):
        validate_paths()


def test_validate_paths_raises_on_out_of_bounds(monkeypatch: pytest.MonkeyPatch) -> None:
    """An out-of-bounds coordinate should raise ValueError."""
    patched = {color: list(path) for color, path in PATHS.items()}
    patched[PlayerColor.BLUE] = list(PATHS[PlayerColor.BLUE])
    patched[PlayerColor.BLUE][5] = (9, 0)  # row 9 is out of range
    monkeypatch.setattr("app.game.board.PATHS", patched)
    with pytest.raises(ValueError, match="out of the 9×9 grid bounds"):
        validate_paths()


def test_validate_paths_raises_on_duplicate(monkeypatch: pytest.MonkeyPatch) -> None:
    """A duplicate coordinate in a path should raise ValueError."""
    patched = {color: list(path) for color, path in PATHS.items()}
    green_path = list(PATHS[PlayerColor.GREEN])
    green_path[10] = green_path[5]  # introduce duplicate
    patched[PlayerColor.GREEN] = green_path
    monkeypatch.setattr("app.game.board.PATHS", patched)
    with pytest.raises(ValueError, match="duplicate"):
        validate_paths()


def test_validate_paths_raises_if_not_ending_at_center(monkeypatch: pytest.MonkeyPatch) -> None:
    """A path that does not end at CENTER should raise ValueError."""
    patched = {color: list(path) for color, path in PATHS.items()}
    yellow_path = list(PATHS[PlayerColor.YELLOW])
    yellow_path[-1] = (3, 3)  # wrong terminal square
    patched[PlayerColor.YELLOW] = yellow_path
    monkeypatch.setattr("app.game.board.PATHS", patched)
    with pytest.raises(ValueError, match="CENTER"):
        validate_paths()
