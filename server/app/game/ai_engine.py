"""AI Move Selection Engine for Ashta Chamma.

Provides difficulty-aware move selection for AI opponents without any
client-side exposure of scoring internals.

Difficulty levels and their strategies:
- Easy  (Bala)   — uniform random selection from legal moves.
- Medium (Kamala) — prefer captures (2×) and advancing the furthest-back
                    pawn (1.5×); also rewards releasing home pawns.
- Hard  (Surya)  — full weighted scoring: capture opportunity, path
                    progress, pawn safety (proximity to safe squares),
                    blocking opponents, and vulnerability reduction.

Strategy weights are loaded from the ``ai_personas.strategy_weights``
JSONB column so that difficulty tuning requires no code changes.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Board constants (derived from legacy path.py / helper.py analysis)
# ---------------------------------------------------------------------------

# Safe squares: captures cannot happen here; multiple players may stack.
SAFE_SQUARES: frozenset[tuple[int, int]] = frozenset(
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

# Each player's path has PATH_LENGTH positions (0 = home base, PATH_LENGTH-1 = finish).
PATH_LENGTH: int = 50

# Path index at which the inner home-stretch begins (player-specific safe corridor).
PATH_INNER_START: int = 25

# Sentinel indices for convenient comparisons.
HOME_PATH_INDEX: int = 0
FINISH_PATH_INDEX: int = PATH_LENGTH - 1  # == 49

# Worst-case Manhattan distance on the 9×9 board — used to normalise proximity scores.
_MAX_BOARD_DISTANCE: int = 16


# ---------------------------------------------------------------------------
# Difficulty level enum
# ---------------------------------------------------------------------------


class DifficultyLevel(str, Enum):
    """AI difficulty levels matching the ``ai_personas.difficulty_level`` DB enum."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LegalMove:
    """A validated, pre-computed move option that the AI may select.

    The game state machine produces these objects before invoking the AI
    engine, so the engine is never responsible for move legality checking.
    """

    pawn_id: str
    """Unique identifier for the pawn (e.g. ``"p0_pawn2"`` for player 0, pawn 2)."""

    player_index: int
    """Which player (0–3) owns this pawn."""

    from_path_index: int
    """Path index *before* the move.  0 = home base (not yet released)."""

    to_path_index: int
    """Path index *after* the move.  FINISH_PATH_INDEX = finish square."""

    from_board_pos: tuple[int, int]
    """Board (row, col) position before the move."""

    to_board_pos: tuple[int, int]
    """Board (row, col) position after the move."""

    is_capture: bool = False
    """True when an opponent pawn occupies the destination square."""

    is_release: bool = False
    """True when the pawn is leaving the home base for the first time (roll 1 or 8)."""

    is_finish: bool = False
    """True when the pawn is moving into the final finish square (4, 4)."""

    captured_pawn_id: Optional[str] = None
    """ID of the opponent pawn that will be captured, if any."""


@dataclass(frozen=True)
class PawnState:
    """Snapshot of a single pawn's position used for board context scoring."""

    pawn_id: str
    player_index: int
    path_index: int
    """Current path index; FINISH_PATH_INDEX means the pawn has finished."""

    board_pos: tuple[int, int]
    is_at_home: bool = False
    """Pawn has not yet been released onto the board (path_index == HOME_PATH_INDEX)."""

    is_finished: bool = False
    """Pawn has already reached the finish square."""


@dataclass
class GameSession:
    """Minimal game context required by the AI engine to evaluate moves."""

    room_id: str
    current_player_index: int
    roll_value: int
    legal_moves: list[LegalMove]
    """Pre-validated moves the AI may choose from.  Must be non-empty."""

    pawns: list[PawnState] = field(default_factory=list)
    """All pawns on the board (all players) for multi-factor scoring."""


@dataclass
class AIPersona:
    """Configuration for an AI opponent loaded from the ``ai_personas`` table."""

    persona_id: int
    name: str
    difficulty_level: str
    """One of ``"easy"``, ``"medium"``, or ``"hard"``."""

    strategy_weights: dict[str, float] = field(default_factory=dict)
    """JSONB weights from the database.  Override per-key defaults below."""

    think_time_seconds: float = 0.75
    """Nominal delay injected by GameService for realistic pacing."""


# ---------------------------------------------------------------------------
# AI Engine
# ---------------------------------------------------------------------------


class AIEngine:
    """Server-side, difficulty-aware move selector.

    Usage::

        engine = AIEngine()
        pawn_id = engine.select_move(game_session, ai_persona)

    All scoring is done server-side; only the final ``pawn_id`` is returned
    — raw scores are never transmitted to clients.
    """

    # Default strategy weights per difficulty level.
    # The database row's ``strategy_weights`` overrides individual keys,
    # so operators can tune behaviour without code changes.
    _DEFAULT_WEIGHTS: dict[str, dict[str, float]] = {
        DifficultyLevel.EASY: {},
        DifficultyLevel.MEDIUM: {
            "capture_weight": 2.0,
            "progress_weight": 1.5,
            "release_weight": 1.2,
        },
        DifficultyLevel.HARD: {
            "capture_weight": 3.0,
            "progress_weight": 2.0,
            "release_weight": 1.5,
            "safety_weight": 1.8,
            "blocking_weight": 1.6,
            "vulnerability_weight": 1.4,
        },
    }

    # Small noise ceiling for Hard difficulty to prevent purely
    # deterministic play (avoids easy counter-strategies by humans).
    _HARD_NOISE_MAX: float = 0.05

    def select_move(self, game_session: GameSession, ai_persona: AIPersona) -> str:
        """Select the best legal pawn to move and return its ``pawn_id``.

        Guarantees:
        - The returned ``pawn_id`` is always in ``game_session.legal_moves``.
        - Completes within 500 ms for any board state with ≤ 4 legal moves.

        Raises:
            ValueError: if ``game_session.legal_moves`` is empty.
        """
        legal_moves = game_session.legal_moves
        if not legal_moves:
            raise ValueError(
                f"No legal moves available for AI '{ai_persona.name}' "
                f"in room '{game_session.room_id}'."
            )

        level = ai_persona.difficulty_level.lower()

        if level == DifficultyLevel.EASY:
            selected = self._select_random(legal_moves)
        elif level == DifficultyLevel.MEDIUM:
            selected = self._select_medium(game_session, ai_persona)
        elif level == DifficultyLevel.HARD:
            selected = self._select_hard(game_session, ai_persona)
        else:
            # Graceful fallback for unknown future difficulty levels.
            logger.warning(
                "Unknown difficulty '%s' for AI '%s'; falling back to random selection.",
                level,
                ai_persona.name,
            )
            selected = self._select_random(legal_moves)

        logger.debug(
            "AI '%s' (difficulty=%s, room=%s, roll=%d) selected pawn '%s' from %d legal moves.",
            ai_persona.name,
            level,
            game_session.room_id,
            game_session.roll_value,
            selected.pawn_id,
            len(legal_moves),
        )
        return selected.pawn_id

    # ------------------------------------------------------------------
    # Difficulty-specific selectors
    # ------------------------------------------------------------------

    def _select_random(self, legal_moves: list[LegalMove]) -> LegalMove:
        """Easy difficulty: uniform random selection across all legal moves."""
        return random.choice(legal_moves)

    def _select_medium(
        self, game_session: GameSession, ai_persona: AIPersona
    ) -> LegalMove:
        """Medium difficulty: score moves with capture + progress + release heuristics."""
        weights = self._merge_weights(DifficultyLevel.MEDIUM, ai_persona.strategy_weights)

        scored: list[tuple[float, LegalMove]] = []
        for move in game_session.legal_moves:
            capture = self._capture_score(move)
            progress = self._progress_score(move)
            release = self._release_score(move)

            score = (
                weights["capture_weight"] * capture
                + weights["progress_weight"] * progress
                + weights["release_weight"] * release
            )
            scored.append((score, move))
            logger.debug(
                "Medium AI pawn '%s': capture=%.2f progress=%.2f release=%.2f → total=%.4f",
                move.pawn_id,
                capture,
                progress,
                release,
                score,
            )

        return self._pick_best(scored)

    def _select_hard(
        self, game_session: GameSession, ai_persona: AIPersona
    ) -> LegalMove:
        """Hard difficulty: full weighted scoring with random noise for variety."""
        weights = self._merge_weights(DifficultyLevel.HARD, ai_persona.strategy_weights)
        opponent_positions = self._opponent_board_positions(game_session)

        scored: list[tuple[float, LegalMove]] = []
        for move in game_session.legal_moves:
            capture = self._capture_score(move)
            progress = self._progress_score(move)
            release = self._release_score(move)
            safety = self._safety_score(move)
            blocking = self._blocking_score(move, opponent_positions)
            vulnerability = self._vulnerability_score(move, game_session)
            noise = random.uniform(0.0, self._HARD_NOISE_MAX)

            score = (
                weights["capture_weight"] * capture
                + weights["progress_weight"] * progress
                + weights["release_weight"] * release
                + weights["safety_weight"] * safety
                + weights["blocking_weight"] * blocking
                + weights["vulnerability_weight"] * vulnerability
                + noise
            )
            scored.append((score, move))
            logger.debug(
                "Hard AI pawn '%s': capture=%.2f progress=%.2f release=%.2f "
                "safety=%.2f blocking=%.2f vulnerability=%.2f noise=%.4f → total=%.4f",
                move.pawn_id,
                capture,
                progress,
                release,
                safety,
                blocking,
                vulnerability,
                noise,
                score,
            )

        return self._pick_best(scored)

    # ------------------------------------------------------------------
    # Individual scoring components
    # ------------------------------------------------------------------

    def _capture_score(self, move: LegalMove) -> float:
        """Return 1.0 if the move captures an opponent pawn, else 0.0."""
        return 1.0 if move.is_capture else 0.0

    def _progress_score(self, move: LegalMove) -> float:
        """Favour moving the pawn that has progressed the least (furthest-back).

        Returns a value in [0, 1] that is highest for pawns near the start
        of the track, encouraging the AI to distribute risk by advancing
        laggard pawns.  Home-base pawns are handled by ``_release_score``
        instead and return 0.0 here.
        """
        if move.is_release or move.from_path_index <= HOME_PATH_INDEX:
            # release_score rewards entering the board; don't double-count.
            return 0.0
        # Normalise against the last *on-board* index before the finish.
        usable_length = FINISH_PATH_INDEX - 1
        return max(0.0, 1.0 - (move.from_path_index / usable_length))

    def _release_score(self, move: LegalMove) -> float:
        """Return 1.0 if the move releases a pawn from the home base, else 0.0."""
        return 1.0 if move.is_release else 0.0

    def _safety_score(self, move: LegalMove) -> float:
        """Score the safety of the destination square.

        Returns 1.0 for a recognised safe square.  For other squares,
        returns a partial score based on the inverse Manhattan distance to
        the nearest safe square (closer = safer).
        """
        if move.to_board_pos in SAFE_SQUARES:
            return 1.0

        min_dist = min(
            abs(move.to_board_pos[0] - sq[0]) + abs(move.to_board_pos[1] - sq[1])
            for sq in SAFE_SQUARES
        )
        return max(0.0, 1.0 - (min_dist / _MAX_BOARD_DISTANCE))

    def _blocking_score(
        self,
        move: LegalMove,
        opponent_positions: set[tuple[int, int]],
    ) -> float:
        """Estimate how much the move interferes with nearby opponent pawns.

        Counts opponent pawns orthogonally adjacent to the destination
        and normalises to [0, 1].  Safe-square destinations score 0 because
        no capture can occur there — the capture_score already handles that
        incentive via the is_capture flag.
        """
        if move.to_board_pos in SAFE_SQUARES:
            return 0.0

        row, col = move.to_board_pos
        adjacent: set[tuple[int, int]] = {
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        }
        nearby_count = len(adjacent & opponent_positions)
        # Up to 4 adjacent opponents → maximum score 1.0
        return min(1.0, nearby_count / 4.0)

    def _vulnerability_score(
        self, move: LegalMove, game_session: GameSession
    ) -> float:
        """Reward moving away from a threatened, non-safe position.

        Returns a score in [0, 1] that is higher when the current position
        is close to an opponent pawn and is *not* on a safe square.
        Returns 0.0 for home-base or already-safe positions.
        """
        if move.is_release:
            return 0.0
        if move.from_board_pos in SAFE_SQUARES:
            return 0.0

        threat_radius = 4  # Manhattan distance threshold for "danger"
        opponent_pawns = [
            p
            for p in game_session.pawns
            if p.player_index != game_session.current_player_index
            and not p.is_finished
            and not p.is_at_home
        ]

        for opp in opponent_pawns:
            dist = abs(move.from_board_pos[0] - opp.board_pos[0]) + abs(
                move.from_board_pos[1] - opp.board_pos[1]
            )
            if dist <= threat_radius:
                # Closer threat → higher incentive to move away.
                return min(1.0, (threat_radius - dist + 1) / (threat_radius + 1))

        return 0.0

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge_weights(
        self,
        difficulty: DifficultyLevel,
        persona_weights: dict[str, float],
    ) -> dict[str, float]:
        """Return effective weights: defaults overridden by persona DB values."""
        merged: dict[str, float] = dict(self._DEFAULT_WEIGHTS[difficulty])
        merged.update(persona_weights)
        return merged

    def _opponent_board_positions(
        self, game_session: GameSession
    ) -> set[tuple[int, int]]:
        """Return the set of board positions occupied by active opponent pawns."""
        return {
            p.board_pos
            for p in game_session.pawns
            if p.player_index != game_session.current_player_index
            and not p.is_finished
            and not p.is_at_home
        }

    def _pick_best(self, scored: list[tuple[float, LegalMove]]) -> LegalMove:
        """Return the LegalMove with the highest score."""
        best_score, best_move = max(scored, key=lambda item: item[0])
        logger.debug(
            "Selected pawn '%s' with score %.4f (from %d candidates).",
            best_move.pawn_id,
            best_score,
            len(scored),
        )
        return best_move
