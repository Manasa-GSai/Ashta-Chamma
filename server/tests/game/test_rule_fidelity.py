"""
Characterization tests — Ashta Chamma game rule fidelity.

These tests encode specific game scenarios derived from the legacy
``helper.py`` and ``game.py`` code and verify that the new game engine
produces identical outcomes.

Scenarios are documented with references to the specific legacy logic
being replicated.  The intent is a living specification: any failure
indicates a rule-fidelity gap that must be fixed in the engine before
the rewrite can proceed.

Color mapping (from legacy game.py):
    R = 0, B = 1, G = 2, Y = 3

Path anatomy (50 positions, index 0–49):
    index  0      — home position (off the inner board)
    indices 1–24  — outer shared track
    indices 25–49 — inner home-stretch (player-specific)
    index 49      — center square (4,4), win destination
"""

from __future__ import annotations

import pytest

from app.game.engine import (
    CENTER_INDEX,
    HOME_INDEX,
    INNER_PATH_THRESHOLD,
    NUM_PLAYERS,
    PATHS,
    RELEASE_ROLLS,
    SAFE_SQUARES,
    GameSession,
    GameState,
    MoveResult,
    PawnState,
    compute_new_path_index,
    get_possible_moves,
)

# ---------------------------------------------------------------------------
# Test-state construction helpers
# ---------------------------------------------------------------------------

PawnOverrides = dict[tuple[int, int], int]  # (color, pawn_id) -> path_index


def _all_home_pawns() -> list[PawnState]:
    """Return 16 pawns (4 per player) all sitting at their home position."""
    return [
        PawnState(color=c, pawn_id=p, path_index=HOME_INDEX)
        for c in range(NUM_PLAYERS)
        for p in range(4)
    ]


def _make_state(
    overrides: PawnOverrides | None = None,
    current_player: int = 0,
    kills_made: list[bool] | None = None,
) -> GameState:
    """
    Build a ``GameState`` with all pawns at home, then apply *overrides*.

    ``overrides`` maps ``(color, pawn_id)`` to a ``path_index``.
    ``kills_made`` defaults to all-False if not supplied.
    """
    pawns = _all_home_pawns()
    if overrides:
        for pawn in pawns:
            key = (pawn.color, pawn.pawn_id)
            if key in overrides:
                pawn.path_index = overrides[key]
    return GameState(
        pawns=pawns,
        current_player=current_player,
        kills_made=kills_made if kills_made is not None else [False] * NUM_PLAYERS,
    )


def _session(
    overrides: PawnOverrides | None = None,
    current_player: int = 0,
    kills_made: list[bool] | None = None,
) -> GameSession:
    """Convenience wrapper that builds a state and wraps it in a session."""
    return GameSession(_make_state(overrides, current_player, kills_made))


# ---------------------------------------------------------------------------
# Scenario Group 1 — Pawn release from home
#
# Legacy reference: helper.py move() + architecture rule
#     "Only values 1 or 8 allow entering a new pawn onto the board."
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("roll", [1, 8])
def test_home_pawn_can_release_on_roll_1_or_8(roll: int) -> None:
    """
    Pawn at home (index 0) can enter the board on a roll of 1 or 8.

    Verifies: acceptance criterion #3.
    Legacy: RELEASE_ROLLS = {1, 8} (game rule, enforced in new engine).
    """
    session = _session()  # all pawns at home, current_player=0

    moveable = session.get_possible_moves(roll=roll)

    # At least one pawn should be eligible to move
    assert len(moveable) > 0, (
        f"Expected at least one pawn to be moveable on roll={roll}, got none"
    )

    # Apply the move for the first eligible pawn and verify the new position
    pawn_id = moveable[0]
    result: MoveResult = session.apply_move(pawn_id=pawn_id, roll=roll)
    moved_pawn = result.new_state.get_pawn(color=0, pawn_id=pawn_id)

    assert moved_pawn.path_index == roll, (
        f"Home pawn after roll={roll} should be at path index {roll}, "
        f"got {moved_pawn.path_index}"
    )


@pytest.mark.parametrize("roll", [2, 3])
def test_home_pawn_cannot_release_on_roll_2_or_3(roll: int) -> None:
    """
    Pawn at home cannot enter the board on a roll of 2 or 3.

    Verifies: acceptance criterion #3 (inverse — non-release rolls).
    If ALL pawns are at home and no release roll is thrown, no moves exist.
    """
    session = _session()  # all pawns at home

    moveable = session.get_possible_moves(roll=roll)

    assert moveable == [], (
        f"No pawn should be moveable on roll={roll} when all are at home, "
        f"got moveable pawn_ids={moveable}"
    )


def test_home_pawn_no_release_on_roll_4_but_extra_turn_granted() -> None:
    """
    Roll of 4 grants an extra turn but does NOT release a pawn from home.

    Verifies: RELEASE_ROLLS = {1,8}; EXTRA_TURN_ROLLS = {4,8}.
    Legacy reference: game.py  ``if int(Num) % 4 == 0`` — extra turn logic.
    """
    session = _session()  # all pawns at home

    moveable = session.get_possible_moves(roll=4)

    # No pawn at home can be released by a roll of 4
    assert moveable == [], (
        "Roll of 4 should not release any home pawn"
    )

    # The roll itself is still an extra-turn roll
    assert GameSession.is_extra_turn_roll(4) is True


# ---------------------------------------------------------------------------
# Scenario Group 2 — Index-24 blocking rule
#
# Legacy reference: helper.py move()
#     ``if(k+N>24 and not isKill): newPosition=k``
#
# A pawn on the outer track (index ≤ 24) cannot cross into the inner
# home-stretch (index > 24) unless the player has made at least one capture.
# ---------------------------------------------------------------------------

def test_inner_path_entry_allowed_when_kill_was_made() -> None:
    """
    Pawn at path index 22, roll=3 moves to index 25 when kill_made=True.

    Verifies: acceptance criterion #4.
    k=22, k+roll=25 > 24 — would be blocked without a prior kill.
    With kills_made=True the blocking condition is lifted.
    """
    # Place player-0 pawn-0 at index 22; mark that a kill was made
    session = _session(
        overrides={(0, 0): 22},
        kills_made=[True, False, False, False],
    )

    moveable = session.get_possible_moves(roll=3)
    assert 0 in moveable, "Pawn at index 22 should be moveable with roll=3 after a kill"

    result = session.apply_move(pawn_id=0, roll=3)
    moved_pawn = result.new_state.get_pawn(color=0, pawn_id=0)

    assert moved_pawn.path_index == 25, (
        f"Pawn should advance to index 25, got {moved_pawn.path_index}"
    )


def test_inner_path_entry_blocked_without_kill() -> None:
    """
    Pawn at path index 22, roll=3 stays at 22 when no kill has been made.

    Verifies: index-24 blocking rule (criteria reference, constraints section).
    k=22, k+roll=25 > INNER_PATH_THRESHOLD(24) and kill_made=False → stay.
    """
    session = _session(
        overrides={(0, 0): 22},
        kills_made=[False, False, False, False],  # no kill yet
    )

    moveable = session.get_possible_moves(roll=3)

    assert 0 not in moveable, (
        "Pawn at index 22 should be blocked from crossing threshold without a kill"
    )

    # Verify via the pure helper too
    pawn = session.state.get_pawn(0, 0)
    new_idx = compute_new_path_index(pawn, roll=3, kill_made=False)
    assert new_idx == 22, f"Expected pawn to stay at 22, computed {new_idx}"


# ---------------------------------------------------------------------------
# Scenario Group 3 — Capture rules
#
# Legacy reference: helper.py checkEnemy() + game.py
#     ``enemy = checkEnemy(pawn.Tup, pawn.color)``
#     ``if enemy != None: enemy.goToStart(cells); k[pawn.color]=True``
# ---------------------------------------------------------------------------

def test_capture_on_non_safe_square() -> None:
    """
    Landing on an enemy pawn occupying a non-safe square captures it.

    After capture:
    - Enemy pawn returns to path index 0 (home).
    - Capturing player's kills_made flag is set to True.
    - An extra turn is granted.

    Verifies: acceptance criterion #5.
    """
    # PATHS[0][5] = (2,1) — not a safe square.
    # Different players' paths share board squares on the outer track, so we
    # must place the enemy at the index in player-1's path that maps to the
    # same board coordinate (2,1).
    target_index = 5
    target_pos = PATHS[0][target_index]  # (2,1)
    assert target_pos not in SAFE_SQUARES, (
        "Test setup error: target must be a non-safe square"
    )
    # Find where (2,1) sits in player-1's path (PATHS[1][23] = (2,1))
    p1_index = PATHS[1].index(target_pos)

    # Player-0 pawn-0 at index 2 will roll 3 and land on index 5 = (2,1).
    # Player-1 pawn-0 already occupies the same board square via its own path.
    session = _session(
        overrides={
            (0, 0): 2,          # player-0 pawn-0 at index 2 in path-0
            (1, 0): p1_index,   # player-1 pawn-0 at SAME board square via path-1
        },
        current_player=0,
    )

    result: MoveResult = session.apply_move(pawn_id=0, roll=3)

    # Capturing player's pawn should now be at index 5
    attacker = result.new_state.get_pawn(color=0, pawn_id=0)
    assert attacker.path_index == target_index

    # Captured pawn should be back at home
    captured_pawn = result.new_state.get_pawn(color=1, pawn_id=0)
    assert captured_pawn.path_index == HOME_INDEX, (
        f"Captured pawn should be at home (index 0), got {captured_pawn.path_index}"
    )

    # Capture grants extra turn
    assert result.extra_turn is True, "Capture must grant an extra turn"

    # kills_made flag for player 0 must now be True
    assert result.new_state.kills_made[0] is True


def test_no_capture_on_safe_square() -> None:
    """
    Landing on an enemy pawn that occupies a safe square does NOT capture it.

    Verifies: acceptance criterion #6.
    Legacy reference: helper.py checkEnemy()
        ``if position not in safe_places: ... else: (implicit) return None``
    """
    # (1,4) is a safe square; it is PATHS[0][1]
    safe_pos = (1, 4)
    assert safe_pos in SAFE_SQUARES, "Test setup error: (1,4) must be safe"

    p0_idx_of_safe = PATHS[0].index(safe_pos)  # == 1
    # Find where (1,4) appears in player-1's path
    p1_idx_of_safe = PATHS[1].index(safe_pos)

    # Player-0 pawn-0 moves to the safe square where player-1 pawn-0 already sits
    session = _session(
        overrides={
            (0, 0): p0_idx_of_safe - 1,   # one step before safe square
            (1, 0): p1_idx_of_safe,        # enemy on the safe square
        },
        current_player=0,
    )

    result: MoveResult = session.apply_move(pawn_id=0, roll=1)

    # Attacker should be on the safe square
    attacker = result.new_state.get_pawn(color=0, pawn_id=0)
    assert attacker.path_index == p0_idx_of_safe

    # Enemy pawn must NOT have been sent home
    enemy = result.new_state.get_pawn(color=1, pawn_id=0)
    assert enemy.path_index == p1_idx_of_safe, (
        "Enemy pawn on safe square must not be captured"
    )

    # No capture → no capture-based extra turn
    assert result.captured_pawn is None


# ---------------------------------------------------------------------------
# Scenario Group 4 — Extra turn rules
#
# Legacy reference: game.py
#     ``if int(Num) % 4 == 0:  # extra turn on 4 or 8``
#     ``if enemy != None: ... changeTurn = False  # extra turn on capture``
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "roll, expected_extra_turn",
    [
        (4, True),   # 4 % 4 == 0 → extra turn
        (8, True),   # 8 % 4 == 0 → extra turn
        (1, False),  # 1 % 4 != 0 → no extra turn
        (2, False),  # 2 % 4 != 0 → no extra turn
        (3, False),  # 3 % 4 != 0 → no extra turn
    ],
)
def test_extra_turn_roll_rules(roll: int, expected_extra_turn: bool) -> None:
    """
    Rolls 4 and 8 grant extra turn; rolls 1, 2, 3 do not.

    Verifies: acceptance criteria #7 (roll of 4 or 8 → extra turn).
    Legacy reference: game.py ``if int(Num) % 4 == 0``.
    """
    # Use a pawn already on the board (index 2) so moves are valid for all rolls
    # Without kill, roll must not push pawn past index 24
    session = _session(
        overrides={(0, 0): 2},
        kills_made=[False, False, False, False],
    )

    # Verify engine's is_extra_turn_roll() helper
    assert GameSession.is_extra_turn_roll(roll) is expected_extra_turn

    result: MoveResult = session.apply_move(pawn_id=0, roll=roll)

    # Extra turn from roll should match expectation (assuming no capture)
    if result.captured_pawn is None:  # no accidental capture in this setup
        assert result.extra_turn is expected_extra_turn, (
            f"roll={roll}: expected extra_turn={expected_extra_turn}, "
            f"got {result.extra_turn}"
        )


def test_turn_advances_to_next_player_when_no_extra_turn() -> None:
    """
    After a roll without extra-turn and no capture, current_player increments.

    Verifies: turn management with rolls 2 and 3 (no extra turn).
    """
    session = _session(
        overrides={(0, 0): 2},  # player-0 pawn at index 2
    )

    result = session.apply_move(pawn_id=0, roll=2)

    assert result.extra_turn is False
    assert result.new_state.current_player == 1, (
        "After a normal move with roll=2, turn must pass to player 1"
    )


def test_extra_turn_on_capture_regardless_of_roll() -> None:
    """
    A capture always grants an extra turn, even on rolls that would not
    normally do so (rolls 1, 2, 3).

    Verifies: acceptance criterion #8.
    Legacy reference: game.py
        ``if enemy != None: enemy.goToStart(cells); k[pawn.color]=True;
          changeTurn=False``
    """
    # Place player-0 pawn-0 one step before a non-safe enemy
    # PATHS[0][3] = (1,2) — not a safe square
    target_idx = 3
    assert PATHS[0][target_idx] not in SAFE_SQUARES
    target_pos = PATHS[0][target_idx]
    p1_target = PATHS[1].index(target_pos)

    session = _session(
        overrides={
            (0, 0): 2,         # player-0 pawn-0 will roll 1 and land on index 3
            (1, 0): p1_target,  # enemy sitting there
        },
        current_player=0,
    )

    # Roll 1 does NOT normally grant extra turn, but capture overrides that
    result = session.apply_move(pawn_id=0, roll=1)

    assert result.captured_pawn is not None, "A capture should have occurred"
    assert result.extra_turn is True, (
        "Capture must grant extra turn even when roll=1 would not"
    )
    # Turn should NOT have advanced
    assert result.new_state.current_player == 0


def test_same_player_continues_after_extra_turn_roll() -> None:
    """
    After a roll of 4 or 8, current_player does NOT change.

    Verifies: acceptance criterion #7 (same player rolls again).
    """
    session = _session(
        overrides={(0, 0): 2},
    )

    result = session.apply_move(pawn_id=0, roll=4)

    assert result.extra_turn is True
    assert result.new_state.current_player == 0, (
        "Player 0 should still be the current player after a roll of 4"
    )


# ---------------------------------------------------------------------------
# Scenario Group 5 — Center approach and exact landing
#
# Legacy reference: helper.py move()
#     ``elif k+N > len(path)-1 or currentPos==path[-1]: newPosition=k``
# Center is at index 49; len(path)-1 = 49.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "start_index, roll",
    [
        (47, 3),   # 47+3=50 > 49 → overshoot → stay
        (47, 4),   # 47+4=51 > 49 → overshoot → stay (also extra turn roll)
        (46, 4),   # 46+4=50 > 49 → overshoot → stay
        (48, 2),   # 48+2=50 > 49 → overshoot → stay
    ],
)
def test_pawn_cannot_overshoot_center(start_index: int, roll: int) -> None:
    """
    A pawn cannot advance past center (index 49) — it must land exactly.

    Verifies: acceptance criterion #9.
    Legacy reference: ``elif k+N > len(path)-1: newPosition=k``.
    """
    session = _session(
        overrides={(0, 0): start_index},
        kills_made=[True, False, False, False],  # kill made → inner path allowed
    )

    pawn = session.state.get_pawn(0, 0)
    new_idx = compute_new_path_index(pawn, roll=roll, kill_made=True)

    assert new_idx == start_index, (
        f"Pawn at index {start_index} with roll={roll} should stay "
        f"(overshoot), got new_idx={new_idx}"
    )

    # get_possible_moves should exclude this pawn
    moveable = session.get_possible_moves(roll=roll)
    # The pawn may still appear if other pawns block — check specifically
    pawn_in_moveable = 0 in moveable
    # Since the pawn doesn't move, it should NOT be in moveable list
    assert not pawn_in_moveable, (
        f"Pawn at {start_index} should not be moveable with roll={roll} "
        f"(would overshoot center)"
    )


@pytest.mark.parametrize(
    "start_index, roll",
    [
        (48, 1),   # 48+1=49 → exact landing on center
        (46, 3),   # 46+3=49 → exact landing on center
        (47, 2),   # 47+2=49 → exact landing on center
    ],
)
def test_pawn_lands_exactly_on_center(start_index: int, roll: int) -> None:
    """
    A pawn can land exactly on the center square (index 49).

    Verifies: acceptance criterion #9 (positive case — exact landing).
    """
    session = _session(
        overrides={(0, 0): start_index},
        kills_made=[True, False, False, False],
    )

    pawn = session.state.get_pawn(0, 0)
    new_idx = compute_new_path_index(pawn, roll=roll, kill_made=True)

    assert new_idx == CENTER_INDEX, (
        f"Pawn at index {start_index} with roll={roll} should land on "
        f"center (index 49), got {new_idx}"
    )

    moveable = session.get_possible_moves(roll=roll)
    assert 0 in moveable, (
        f"Pawn at {start_index} should be moveable with roll={roll} (exact center landing)"
    )


# ---------------------------------------------------------------------------
# Scenario Group 6 — Friendly blocking
#
# Legacy reference: helper.py possibleMoves()
#     ``for i in pawns:
#           if newPos == i.Tup and newPos not in safe_places: break
#       else: allMoves.append(pawn)``
# ---------------------------------------------------------------------------

def test_friendly_blocking_on_non_safe_square() -> None:
    """
    A pawn cannot move to a square already occupied by a friendly pawn
    when that square is NOT a safe square.

    Verifies: acceptance criterion from constraints (friendly blocking rule).
    """
    # PATHS[0][4] = (1,1) — not a safe square
    blocker_idx = 4
    assert PATHS[0][blocker_idx] not in SAFE_SQUARES, (
        "Test setup error: blocker position must be non-safe"
    )

    session = _session(
        overrides={
            (0, 0): 1,          # pawn-0 will try to roll 3 → land on index 4
            (0, 1): blocker_idx,  # pawn-1 (friendly) already there
        },
        current_player=0,
    )

    moveable = session.get_possible_moves(roll=3)

    assert 0 not in moveable, (
        "Pawn-0 should be blocked from landing on square occupied by friendly pawn-1"
    )


def test_friendly_pawns_can_share_safe_square() -> None:
    """
    Friendly pawns may coexist on a safe square; the target pawn is NOT blocked.

    Verifies: safe-square exception to friendly-blocking.
    """
    # (1,4) is safe and is PATHS[0][1]
    safe_idx = PATHS[0].index((1, 4))  # == 1

    session = _session(
        overrides={
            (0, 0): safe_idx - 1 if safe_idx > 0 else HOME_INDEX,  # one before safe
            (0, 1): safe_idx,  # friendly pawn already on the safe square
        },
        current_player=0,
        kills_made=[True, False, False, False],  # ensure no threshold issues
    )

    moveable = session.get_possible_moves(roll=1)

    assert 0 in moveable, (
        "Pawn-0 should be allowed to land on safe square even with friendly pawn-1 there"
    )


def test_multiple_enemy_pawns_on_safe_square_no_capture() -> None:
    """
    Multiple enemy pawns on a safe square are not captured when the
    current player lands there.

    Verifies: acceptance criterion #6 (safe-square coexistence for all players).
    """
    # (4,7) is a safe square
    safe_pos = (4, 7)
    assert safe_pos in SAFE_SQUARES

    p0_idx = PATHS[0].index(safe_pos)
    p1_idx = PATHS[1].index(safe_pos)
    p2_idx = PATHS[2].index(safe_pos)

    session = _session(
        overrides={
            (0, 0): p0_idx - 1,   # player-0 one step away
            (1, 0): p1_idx,       # two enemies on the safe square
            (2, 0): p2_idx,
        },
        current_player=0,
        kills_made=[True, False, False, False],
    )

    result = session.apply_move(pawn_id=0, roll=1)

    assert result.captured_pawn is None, (
        "No capture should occur when landing on a safe square with enemies"
    )
    # Both enemy pawns remain at their positions
    enemy1 = result.new_state.get_pawn(1, 0)
    enemy2 = result.new_state.get_pawn(2, 0)
    assert enemy1.path_index == p1_idx
    assert enemy2.path_index == p2_idx


# ---------------------------------------------------------------------------
# Scenario Group 7 — Win condition
#
# Legacy reference: helper.py gameDone()
#     ``for pawn in pawns:
#           if pawn.Tup != (4,4): return False
#       return True``
# ---------------------------------------------------------------------------

def test_game_not_over_with_three_pawns_at_center() -> None:
    """
    Game is NOT over when only 3 of 4 pawns have reached the center.

    Verifies: win requires ALL 4 pawns (acceptance criterion #10).
    """
    session = _session(
        overrides={
            (0, 0): CENTER_INDEX,
            (0, 1): CENTER_INDEX,
            (0, 2): CENTER_INDEX,
            (0, 3): 48,  # last pawn one step from center
        },
        kills_made=[True, False, False, False],
    )

    result = session.apply_move(pawn_id=3, roll=2)  # overshoot: 48+2=50>49 → stay

    assert result.game_over is False
    assert session.state.game_over is False


def test_last_pawn_reaching_center_ends_game() -> None:
    """
    Game ends when the 4th pawn of the current player reaches the center.

    Verifies: acceptance criterion #10.
    Legacy reference: game.py ``if gameDone(allPawns[pawn.color]): ...``.
    """
    session = _session(
        overrides={
            (0, 0): CENTER_INDEX,
            (0, 1): CENTER_INDEX,
            (0, 2): CENTER_INDEX,
            (0, 3): 48,  # one step from center
        },
        kills_made=[True, False, False, False],
    )

    result = session.apply_move(pawn_id=3, roll=1)  # 48+1=49 → exact center landing

    assert result.game_over is True, "Game should end when all 4 pawns reach center"
    assert result.new_state.winner == 0, "Player 0 should be declared the winner"
    assert result.new_state.game_over is True


def test_game_ends_with_exact_roll_to_center() -> None:
    """
    All four pawns reach center only when the exact roll lands the last pawn.

    This confirms overshoot prevention and win detection work together:
    the penultimate pawn cannot accidentally win by overshooting.
    """
    # Last pawn at index 47; needs roll=2 to land on 49 exactly
    session = _session(
        overrides={
            (0, 0): CENTER_INDEX,
            (0, 1): CENTER_INDEX,
            (0, 2): CENTER_INDEX,
            (0, 3): 47,
        },
        kills_made=[True, False, False, False],
    )

    # Roll 3 would overshoot (47+3=50>49) — no win
    result_overshoot = session.apply_move(pawn_id=3, roll=3)
    assert result_overshoot.game_over is False
    assert session.state.get_pawn(0, 3).path_index == 47, (
        "Pawn should remain at 47 after overshoot attempt"
    )

    # Roll 2 lands exactly on center — win
    result_win = session.apply_move(pawn_id=3, roll=2)
    assert result_win.game_over is True
    assert result_win.new_state.winner == 0


# ---------------------------------------------------------------------------
# Scenario Group 8 — Mixed / integration scenarios
# ---------------------------------------------------------------------------

def test_pawn_released_from_home_occupies_correct_board_square() -> None:
    """
    After rolling 1, a released pawn sits on the correct board coordinate.

    Smoke test combining release logic and board-position lookup.
    """
    session = _session()  # all at home

    result = session.apply_move(pawn_id=0, roll=1)

    pawn = result.new_state.get_pawn(0, 0)
    assert pawn.path_index == 1
    assert pawn.position == PATHS[0][1], (
        "Board coordinate of released pawn must match PATHS[0][1]"
    )


def test_capture_updates_kills_made_flag() -> None:
    """
    The kills_made flag for the capturing player is set after a capture.

    This is critical because the flag unlocks the inner path (index-24 rule).
    Legacy reference: game.py ``k[pawn.color] = True`` after kill.
    """
    target_pos = PATHS[0][6]  # (3,1) — not safe
    assert target_pos not in SAFE_SQUARES

    p1_target = PATHS[1].index(target_pos)

    session = _session(
        overrides={
            (0, 0): 3,           # will roll 3 to land on index 6
            (1, 0): p1_target,   # enemy sitting there
        },
        current_player=0,
        kills_made=[False, False, False, False],  # starts with no kills
    )

    assert session.state.kills_made[0] is False

    result = session.apply_move(pawn_id=0, roll=3)

    assert result.new_state.kills_made[0] is True, (
        "kills_made[0] must be True after capturing an enemy pawn"
    )


def test_kill_made_flag_enables_inner_path_on_next_move() -> None:
    """
    After making a kill, the same player can immediately cross into
    the inner home-stretch on a subsequent move.

    Integration test verifying: capture → kills_made=True → index-24 unlocked.
    """
    # Target for capture: PATHS[0][25] is (2,6) which IS a safe square; use PATHS[0][26]
    inner_entry = 25  # first inner-path index
    approach_idx = inner_entry - 3  # index 22

    # Ensure we have an enemy to capture on some outer square to unlock the kill flag
    capture_pos = PATHS[0][5]  # (2,1) — not safe
    assert capture_pos not in SAFE_SQUARES
    p1_capture = PATHS[1].index(capture_pos)

    # Two player-0 pawns: pawn-0 makes the kill, pawn-1 is at approach_idx
    session = _session(
        overrides={
            (0, 0): 2,              # will kill enemy at index 5 via roll=3
            (0, 1): approach_idx,   # pawn at index 22 — blocked until kill made
            (1, 0): p1_capture,     # enemy to be captured
        },
        current_player=0,
        kills_made=[False, False, False, False],
    )

    # Step 1: capture with pawn-0 (roll=3 → index 5, kills enemy)
    result1 = session.apply_move(pawn_id=0, roll=3)
    assert result1.new_state.kills_made[0] is True, "Kill flag must be set after capture"
    assert result1.extra_turn is True  # capture grants extra turn

    # Step 2: now pawn-1 at index 22 should be able to cross to index 25 (roll=3)
    moveable = session.get_possible_moves(roll=3)
    assert 1 in moveable, (
        "After making a kill, pawn-1 at index 22 should be able to cross index-24 threshold"
    )

    result2 = session.apply_move(pawn_id=1, roll=3)
    assert result2.new_state.get_pawn(0, 1).path_index == inner_entry


def test_four_player_turn_cycle() -> None:
    """
    Without extra turns or captures, the turn cycles 0→1→2→3→0.

    Verifies: basic turn-advancement across all four players.
    """
    state = _make_state()
    # Give each player one pawn on the board for valid moves
    for color in range(NUM_PLAYERS):
        for p in state.pawns:
            if p.color == color and p.pawn_id == 0:
                p.path_index = 2  # on outer track, can move with roll 1

    session = GameSession(state)

    for expected_current in range(NUM_PLAYERS):
        assert session.state.current_player == expected_current
        result = session.apply_move(pawn_id=0, roll=1)
        assert result.extra_turn is False
        assert result.captured_pawn is None

    # Should have cycled back to player 0
    assert session.state.current_player == 0
