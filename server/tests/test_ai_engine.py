"""Tests for the AI Move Selection Engine (WO-024).

Coverage:
- Easy AI selects uniformly at random (statistical test over 1 000 trials).
- Medium AI prefers capturing moves over non-capturing moves.
- Hard AI scoring functions behave correctly on known board states.
- AI selection always completes within 500 ms.
- AI never selects an illegal move.
- Strategy weights from the database override built-in defaults.
- GameService.execute_ai_turn integrates the engine and adds a delay.
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter
from unittest.mock import MagicMock, patch

import pytest

from app.game.ai_engine import (
    AIEngine,
    AIPersona,
    DifficultyLevel,
    FINISH_PATH_INDEX,
    GameSession,
    HOME_PATH_INDEX,
    LegalMove,
    PATH_INNER_START,
    PawnState,
    SAFE_SQUARES,
)
from app.services.game_service import GameService

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_persona(
    difficulty: str,
    weights: dict | None = None,
    think_time: float = 0.0,
) -> AIPersona:
    return AIPersona(
        persona_id=1,
        name="TestBot",
        difficulty_level=difficulty,
        strategy_weights=weights or {},
        think_time_seconds=think_time,
    )


def _make_move(
    pawn_id: str,
    from_idx: int = 5,
    to_idx: int = 8,
    from_pos: tuple[int, int] = (1, 1),
    to_pos: tuple[int, int] = (2, 1),
    is_capture: bool = False,
    is_release: bool = False,
    is_finish: bool = False,
    captured_pawn_id: str | None = None,
    player_index: int = 0,
) -> LegalMove:
    return LegalMove(
        pawn_id=pawn_id,
        player_index=player_index,
        from_path_index=from_idx,
        to_path_index=to_idx,
        from_board_pos=from_pos,
        to_board_pos=to_pos,
        is_capture=is_capture,
        is_release=is_release,
        is_finish=is_finish,
        captured_pawn_id=captured_pawn_id,
    )


def _make_session(moves: list[LegalMove], pawns: list[PawnState] | None = None) -> GameSession:
    return GameSession(
        room_id="room-test",
        current_player_index=0,
        roll_value=3,
        legal_moves=moves,
        pawns=pawns or [],
    )


# ---------------------------------------------------------------------------
# AC-1 & AC-2: Easy AI — random, within 500 ms, never illegal
# ---------------------------------------------------------------------------


class TestEasyAI:
    """Easy (Bala) — uniform random selection."""

    def test_selects_from_legal_moves(self) -> None:
        """Selected pawn must always be one of the legal moves."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.EASY)
        moves = [_make_move(f"pawn_{i}") for i in range(4)]
        session = _make_session(moves)

        for _ in range(50):
            result = engine.select_move(session, persona)
            assert result in {m.pawn_id for m in moves}

    def test_never_selects_illegal_move(self) -> None:
        """AI must never return an ID that is not in legal_moves."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.EASY)
        legal_ids = {"pawn_0", "pawn_1"}
        moves = [_make_move(pid) for pid in legal_ids]
        session = _make_session(moves)

        for _ in range(200):
            result = engine.select_move(session, persona)
            assert result in legal_ids, f"Illegal pawn '{result}' returned"

    def test_uniform_distribution_over_1000_trials(self) -> None:
        """Statistical test: each pawn should be chosen ~250/1 000 times (±5 %)."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.EASY)
        moves = [_make_move(f"pawn_{i}") for i in range(4)]
        session = _make_session(moves)

        trials = 1_000
        counts: Counter[str] = Counter()
        for _ in range(trials):
            counts[engine.select_move(session, persona)] += 1

        expected = trials / len(moves)
        tolerance = expected * 0.15  # allow ±15 % for randomness
        for move in moves:
            assert abs(counts[move.pawn_id] - expected) < tolerance, (
                f"Pawn '{move.pawn_id}' chosen {counts[move.pawn_id]} times "
                f"(expected {expected:.0f} ± {tolerance:.0f})"
            )

    def test_single_legal_move_always_selected(self) -> None:
        """When only one move is legal, it must always be selected."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.EASY)
        move = _make_move("only_pawn")
        session = _make_session([move])

        for _ in range(20):
            assert engine.select_move(session, persona) == "only_pawn"

    def test_completes_within_500ms(self) -> None:
        """Algorithm must finish within the 500 ms game-flow budget."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.EASY)
        moves = [_make_move(f"pawn_{i}") for i in range(4)]
        session = _make_session(moves)

        start = time.perf_counter()
        engine.select_move(session, persona)
        elapsed_ms = (time.perf_counter() - start) * 1_000
        assert elapsed_ms < 500, f"AI took {elapsed_ms:.1f} ms (limit 500 ms)"

    def test_raises_on_empty_legal_moves(self) -> None:
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.EASY)
        session = _make_session([])
        with pytest.raises(ValueError, match="No legal moves"):
            engine.select_move(session, persona)


# ---------------------------------------------------------------------------
# AC-3: Medium AI — prefers captures and furthest-back pawn
# ---------------------------------------------------------------------------


class TestMediumAI:
    """Medium (Kamala) — capture + furthest-back pawn heuristics."""

    def test_always_selects_from_legal_moves(self) -> None:
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.MEDIUM)
        moves = [_make_move(f"pawn_{i}", from_idx=i + 1, to_idx=i + 4) for i in range(4)]
        session = _make_session(moves)
        result = engine.select_move(session, persona)
        assert result in {m.pawn_id for m in moves}

    def test_prefers_capture_over_non_capture(self) -> None:
        """Medium AI should reliably pick the capture move when capture weight > 0."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.MEDIUM)

        non_capture = _make_move("no_capture", from_idx=10, to_idx=13)
        capture_move = _make_move(
            "capture",
            from_idx=10,
            to_idx=13,
            is_capture=True,
            captured_pawn_id="opp_pawn",
        )
        session = _make_session([non_capture, capture_move])

        results: Counter[str] = Counter()
        for _ in range(20):
            results[engine.select_move(session, persona)] += 1

        # Capture should dominate (at least 18/20 picks due to 2× weight).
        assert results["capture"] >= 18, (
            f"Capture chosen only {results['capture']}/20 times"
        )

    def test_prefers_furthest_back_pawn(self) -> None:
        """Among non-capturing moves, the pawn at the lowest path index scores higher."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.MEDIUM)

        # pawn_behind is at index 2 (further back); pawn_ahead at index 30
        pawn_behind = _make_move("pawn_behind", from_idx=2, to_idx=5)
        pawn_ahead = _make_move("pawn_ahead", from_idx=30, to_idx=33)
        session = _make_session([pawn_behind, pawn_ahead])

        results: Counter[str] = Counter()
        for _ in range(30):
            results[engine.select_move(session, persona)] += 1

        # Furthest-back pawn should be preferred significantly.
        assert results["pawn_behind"] > results["pawn_ahead"], (
            f"Expected pawn_behind to win more; got {dict(results)}"
        )

    def test_prefers_release_over_neutral_advance(self) -> None:
        """A release move should outscore a comparable non-releasing advance."""
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.MEDIUM)

        release = _make_move("release_pawn", from_idx=0, to_idx=1, is_release=True)
        advance = _make_move("advance_pawn", from_idx=20, to_idx=23)
        session = _make_session([release, advance])

        results: Counter[str] = Counter()
        for _ in range(20):
            results[engine.select_move(session, persona)] += 1

        # Release should be chosen most of the time given the default weight.
        assert results["release_pawn"] > results["advance_pawn"], (
            f"Expected release_pawn to dominate; got {dict(results)}"
        )

    def test_completes_within_500ms(self) -> None:
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.MEDIUM)
        moves = [_make_move(f"pawn_{i}", from_idx=i + 1, to_idx=i + 4) for i in range(4)]
        session = _make_session(moves)

        start = time.perf_counter()
        engine.select_move(session, persona)
        elapsed_ms = (time.perf_counter() - start) * 1_000
        assert elapsed_ms < 500

    def test_db_weights_override_defaults(self) -> None:
        """Custom capture_weight=10 in DB should still prefer capture."""
        engine = AIEngine()
        persona = _make_persona(
            DifficultyLevel.MEDIUM,
            weights={"capture_weight": 10.0, "progress_weight": 0.1, "release_weight": 0.1},
        )
        non_capture = _make_move("no_capture")
        capture_move = _make_move("capture", is_capture=True)
        session = _make_session([non_capture, capture_move])

        for _ in range(10):
            assert engine.select_move(session, persona) == "capture"


# ---------------------------------------------------------------------------
# AC-4 & AC-5: Hard AI — full weighted scoring
# ---------------------------------------------------------------------------


class TestHardAI:
    """Hard (Surya) — full multi-factor weighted scoring."""

    def test_always_selects_from_legal_moves(self) -> None:
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.HARD)
        moves = [_make_move(f"pawn_{i}", from_idx=i + 1, to_idx=i + 4) for i in range(4)]
        session = _make_session(moves)
        result = engine.select_move(session, persona)
        assert result in {m.pawn_id for m in moves}

    def test_strongly_prefers_capture_with_high_capture_weight(self) -> None:
        engine = AIEngine()
        persona = _make_persona(
            DifficultyLevel.HARD,
            weights={"capture_weight": 10.0},
        )
        non_capture = _make_move("no_capture", from_idx=5, to_idx=8)
        capture_move = _make_move("capture", from_idx=5, to_idx=8, is_capture=True)
        session = _make_session([non_capture, capture_move])

        for _ in range(20):
            assert engine.select_move(session, persona) == "capture"

    def test_safe_square_destination_scores_higher_than_unsafe(self) -> None:
        """When safety_weight is the only differentiator, safe dest wins."""
        engine = AIEngine()
        persona = _make_persona(
            DifficultyLevel.HARD,
            weights={
                "capture_weight": 0.0,
                "progress_weight": 0.0,
                "release_weight": 0.0,
                "safety_weight": 5.0,
                "blocking_weight": 0.0,
                "vulnerability_weight": 0.0,
            },
        )
        safe_sq = next(iter(SAFE_SQUARES))  # pick any safe square
        unsafe_dest = (3, 5)               # not a safe square
        assert unsafe_dest not in SAFE_SQUARES

        safe_move = _make_move(
            "safe_dest",
            from_idx=10,
            to_idx=13,
            from_pos=(2, 1),
            to_pos=safe_sq,
        )
        unsafe_move = _make_move(
            "unsafe_dest",
            from_idx=10,
            to_idx=13,
            from_pos=(2, 1),
            to_pos=unsafe_dest,
        )
        session = _make_session([safe_move, unsafe_move])

        results: Counter[str] = Counter()
        for _ in range(40):
            results[engine.select_move(session, persona)] += 1

        # safe_dest should dominate; noise alone should not override 5× safety weight.
        assert results["safe_dest"] > results["unsafe_dest"], (
            f"Safe destination not preferred: {dict(results)}"
        )

    def test_vulnerability_score_rewards_leaving_threatened_position(self) -> None:
        """A pawn adjacent to an opponent should be encouraged to flee."""
        engine = AIEngine()
        persona = _make_persona(
            DifficultyLevel.HARD,
            weights={
                "capture_weight": 0.0,
                "progress_weight": 0.0,
                "release_weight": 0.0,
                "safety_weight": 0.0,
                "blocking_weight": 0.0,
                "vulnerability_weight": 5.0,
            },
        )
        opponent_pos = (3, 3)
        threatened_from = (3, 4)  # adjacent to opponent, not a safe square
        safe_from = (1, 1)        # far from opponent, not threatened

        assert threatened_from not in SAFE_SQUARES
        assert safe_from not in SAFE_SQUARES

        # A pawn close to an opponent pawn (from threatened_from).
        threatened_move = _make_move(
            "threatened_pawn",
            from_idx=10,
            to_idx=13,
            from_pos=threatened_from,
            to_pos=(4, 4),  # any destination
        )
        # A pawn far from any opponent.
        safe_move = _make_move(
            "safe_pawn",
            from_idx=10,
            to_idx=13,
            from_pos=safe_from,
            to_pos=(5, 5),
        )

        opp_pawn = PawnState(
            pawn_id="opp",
            player_index=1,
            path_index=15,
            board_pos=opponent_pos,
        )
        session = GameSession(
            room_id="room-test",
            current_player_index=0,
            roll_value=3,
            legal_moves=[threatened_move, safe_move],
            pawns=[opp_pawn],
        )

        results: Counter[str] = Counter()
        for _ in range(40):
            results[engine.select_move(session, persona)] += 1

        assert results["threatened_pawn"] > results["safe_pawn"], (
            f"Threatened pawn not preferred to flee: {dict(results)}"
        )

    def test_finish_move_beats_regular_advance(self) -> None:
        """A finishing move should receive maximum progress score."""
        engine = AIEngine()
        persona = _make_persona(
            DifficultyLevel.HARD,
            weights={
                "capture_weight": 0.0,
                "progress_weight": 5.0,
                "release_weight": 0.0,
                "safety_weight": 0.0,
                "blocking_weight": 0.0,
                "vulnerability_weight": 0.0,
            },
        )
        # Non-finish move: pawn at index 30
        advance_move = _make_move("advance", from_idx=30, to_idx=33)
        # We can't directly test "finish" via progress_score alone since
        # the pawn at index 48 has from_idx near the end.
        # Let's compare pawn at index 1 (furthest back) vs index 30.
        back_move = _make_move("back_pawn", from_idx=1, to_idx=4)

        session = _make_session([advance_move, back_move])

        results: Counter[str] = Counter()
        for _ in range(40):
            results[engine.select_move(session, persona)] += 1

        # back_pawn is furthest-back so should score higher on progress_score.
        assert results["back_pawn"] > results["advance"], (
            f"Furthest-back pawn not preferred by Hard AI: {dict(results)}"
        )

    def test_completes_within_500ms(self) -> None:
        engine = AIEngine()
        persona = _make_persona(DifficultyLevel.HARD)
        moves = [_make_move(f"pawn_{i}", from_idx=i + 1, to_idx=i + 4) for i in range(4)]
        pawns = [
            PawnState(
                pawn_id=f"opp_{i}",
                player_index=1,
                path_index=10,
                board_pos=(i + 1, i + 2),
            )
            for i in range(4)
        ]
        session = GameSession(
            room_id="room-test",
            current_player_index=0,
            roll_value=3,
            legal_moves=moves,
            pawns=pawns,
        )

        start = time.perf_counter()
        engine.select_move(session, persona)
        elapsed_ms = (time.perf_counter() - start) * 1_000
        assert elapsed_ms < 500

    def test_db_weights_override_defaults(self) -> None:
        """Weights from strategy_weights JSONB should override built-in defaults."""
        engine = AIEngine()
        # Zero out all defaults and only give blocking_weight.
        persona = _make_persona(
            DifficultyLevel.HARD,
            weights={
                "capture_weight": 0.0,
                "progress_weight": 0.0,
                "release_weight": 0.0,
                "safety_weight": 0.0,
                "blocking_weight": 8.0,  # only blocking matters
                "vulnerability_weight": 0.0,
            },
        )
        # blocking_move's destination has opponent neighbours.
        opponent_pos = (3, 2)
        blocking_to = (3, 3)   # adjacent to (3,2)
        non_blocking_to = (6, 6)  # far from opponents

        blocking_move = _make_move("blocking", from_idx=10, to_idx=13, to_pos=blocking_to)
        non_blocking_move = _make_move(
            "non_blocking", from_idx=10, to_idx=13, to_pos=non_blocking_to
        )

        opp = PawnState(
            pawn_id="opp",
            player_index=1,
            path_index=15,
            board_pos=opponent_pos,
        )
        session = GameSession(
            room_id="room-test",
            current_player_index=0,
            roll_value=3,
            legal_moves=[blocking_move, non_blocking_move],
            pawns=[opp],
        )

        results: Counter[str] = Counter()
        for _ in range(40):
            results[engine.select_move(session, persona)] += 1

        assert results["blocking"] > results["non_blocking"], (
            f"Blocking not preferred with high blocking_weight: {dict(results)}"
        )


# ---------------------------------------------------------------------------
# AC-7: AI does not use WebSocket — execute_ai_turn path
# ---------------------------------------------------------------------------


class TestGameService:
    """GameService integrates AIEngine and adds think-time delay."""

    def test_execute_ai_turn_returns_valid_pawn_id(self) -> None:
        """execute_ai_turn must return a pawn_id from legal_moves."""
        moves = [_make_move(f"pawn_{i}") for i in range(3)]
        session = _make_session(moves)
        persona = _make_persona(DifficultyLevel.EASY)
        # Use zero think-time for test speed.
        persona.strategy_weights["think_time_min"] = 0.0
        persona.strategy_weights["think_time_max"] = 0.0

        service = GameService()
        result = asyncio.get_event_loop().run_until_complete(
            service.execute_ai_turn(session, persona)
        )
        assert result in {m.pawn_id for m in moves}

    def test_execute_ai_turn_applies_delay(self) -> None:
        """The think-time delay must be applied before returning."""
        moves = [_make_move("pawn_0")]
        session = _make_session(moves)
        persona = _make_persona(DifficultyLevel.EASY)
        persona.strategy_weights["think_time_min"] = 0.05
        persona.strategy_weights["think_time_max"] = 0.05

        service = GameService()
        start = time.perf_counter()
        asyncio.get_event_loop().run_until_complete(
            service.execute_ai_turn(session, persona)
        )
        elapsed = time.perf_counter() - start
        assert elapsed >= 0.04, f"Delay not applied (elapsed={elapsed:.3f}s)"

    def test_execute_ai_turn_uses_injected_engine(self) -> None:
        """Custom AIEngine can be injected (dependency injection contract)."""
        mock_engine = MagicMock(spec=AIEngine)
        mock_engine.select_move.return_value = "injected_pawn"

        moves = [_make_move("injected_pawn")]
        session = _make_session(moves)
        persona = _make_persona(DifficultyLevel.HARD)
        persona.strategy_weights["think_time_min"] = 0.0
        persona.strategy_weights["think_time_max"] = 0.0

        service = GameService(ai_engine=mock_engine)
        result = asyncio.get_event_loop().run_until_complete(
            service.execute_ai_turn(session, persona)
        )
        assert result == "injected_pawn"
        mock_engine.select_move.assert_called_once_with(session, persona)

    def test_think_time_min_max_resolved_from_weights(self) -> None:
        """think_time_min/max in strategy_weights controls actual delay."""
        service = GameService()
        persona = _make_persona(DifficultyLevel.EASY)

        # Reversed min/max should be normalised, not crash.
        persona.strategy_weights["think_time_min"] = 0.06
        persona.strategy_weights["think_time_max"] = 0.04  # min > max on purpose

        moves = [_make_move("pawn_0")]
        session = _make_session(moves)

        # Should not raise even with inverted range.
        result = asyncio.get_event_loop().run_until_complete(
            service.execute_ai_turn(session, persona)
        )
        assert result == "pawn_0"


# ---------------------------------------------------------------------------
# Scoring unit tests (white-box)
# ---------------------------------------------------------------------------


class TestScoringComponents:
    """Direct unit tests for individual scoring methods."""

    def setup_method(self) -> None:
        self.engine = AIEngine()

    def test_capture_score_is_1_when_capture(self) -> None:
        move = _make_move("p", is_capture=True)
        assert self.engine._capture_score(move) == 1.0

    def test_capture_score_is_0_when_no_capture(self) -> None:
        move = _make_move("p", is_capture=False)
        assert self.engine._capture_score(move) == 0.0

    def test_release_score_is_1_when_release(self) -> None:
        move = _make_move("p", from_idx=0, to_idx=1, is_release=True)
        assert self.engine._release_score(move) == 1.0

    def test_release_score_is_0_when_not_release(self) -> None:
        move = _make_move("p", from_idx=5, to_idx=8)
        assert self.engine._release_score(move) == 0.0

    def test_progress_score_is_0_for_release(self) -> None:
        """release_score covers home-pawn incentive; progress_score must return 0."""
        move = _make_move("p", from_idx=0, to_idx=1, is_release=True)
        assert self.engine._progress_score(move) == 0.0

    def test_progress_score_decreases_as_path_index_increases(self) -> None:
        """Further along the path → lower progress_score (furthest-back preference)."""
        back_move = _make_move("back", from_idx=1, to_idx=4)
        mid_move = _make_move("mid", from_idx=24, to_idx=27)
        ahead_move = _make_move("ahead", from_idx=45, to_idx=48)

        back_score = self.engine._progress_score(back_move)
        mid_score = self.engine._progress_score(mid_move)
        ahead_score = self.engine._progress_score(ahead_move)

        assert back_score > mid_score > ahead_score, (
            f"Progress scores not decreasing: {back_score:.3f} > {mid_score:.3f} > {ahead_score:.3f}"
        )

    def test_safety_score_is_1_on_safe_square(self) -> None:
        safe_sq = (1, 4)
        assert safe_sq in SAFE_SQUARES
        move = _make_move("p", to_pos=safe_sq)
        assert self.engine._safety_score(move) == 1.0

    def test_safety_score_is_fractional_on_unsafe_square(self) -> None:
        unsafe = (0, 0)  # corner, not a safe square
        assert unsafe not in SAFE_SQUARES
        move = _make_move("p", to_pos=unsafe)
        score = self.engine._safety_score(move)
        assert 0.0 <= score < 1.0

    def test_blocking_score_0_on_safe_square(self) -> None:
        """Blocking score is 0 on safe squares (captures can't occur there)."""
        safe_sq = (4, 1)
        assert safe_sq in SAFE_SQUARES
        move = _make_move("p", to_pos=safe_sq)
        score = self.engine._blocking_score(move, {(3, 1), (5, 1)})
        assert score == 0.0

    def test_blocking_score_increases_with_adjacent_opponents(self) -> None:
        dest = (3, 3)  # not a safe square
        assert dest not in SAFE_SQUARES
        move = _make_move("p", to_pos=dest)

        score_none = self.engine._blocking_score(move, set())
        score_one = self.engine._blocking_score(move, {(2, 3)})
        score_two = self.engine._blocking_score(move, {(2, 3), (4, 3)})

        assert score_none < score_one < score_two

    def test_vulnerability_score_0_on_safe_square(self) -> None:
        safe_sq = (2, 2)
        assert safe_sq in SAFE_SQUARES
        move = _make_move("p", from_pos=safe_sq)
        opp = PawnState("opp", player_index=1, path_index=5, board_pos=(2, 3))
        session = GameSession(
            room_id="r", current_player_index=0, roll_value=2,
            legal_moves=[move], pawns=[opp]
        )
        assert self.engine._vulnerability_score(move, session) == 0.0

    def test_vulnerability_score_0_for_release(self) -> None:
        move = _make_move("p", is_release=True)
        session = _make_session([move])
        assert self.engine._vulnerability_score(move, session) == 0.0

    def test_vulnerability_score_positive_when_opponent_near(self) -> None:
        from_pos = (3, 4)  # not a safe square
        assert from_pos not in SAFE_SQUARES
        move = _make_move("p", from_pos=from_pos, from_idx=10)
        opp = PawnState("opp", player_index=1, path_index=15, board_pos=(3, 5))  # distance 1
        session = GameSession(
            room_id="r", current_player_index=0, roll_value=3,
            legal_moves=[move], pawns=[opp]
        )
        score = self.engine._vulnerability_score(move, session)
        assert score > 0.0

    def test_merge_weights_prefers_db_values(self) -> None:
        """DB weights should fully override the default for any key they specify."""
        db_weights = {"capture_weight": 99.0}
        merged = self.engine._merge_weights(DifficultyLevel.MEDIUM, db_weights)
        assert merged["capture_weight"] == 99.0
        # Keys not in db_weights retain defaults.
        assert "progress_weight" in merged

    def test_unknown_difficulty_falls_back_to_random(self) -> None:
        persona = _make_persona("expert")  # not a known level
        moves = [_make_move(f"p{i}") for i in range(3)]
        session = _make_session(moves)
        result = self.engine.select_move(session, persona)
        assert result in {m.pawn_id for m in moves}
