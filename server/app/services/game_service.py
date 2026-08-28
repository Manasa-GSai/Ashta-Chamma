"""Game service — orchestrates AI turn execution.

This is the integration point between the game state machine (WO-013) and
the AI engine.  Human player moves arrive via the WebSocket router; AI
player moves are initiated here so that AI opponents never need a network
connection.

Responsibilities:
- Receive game session context when it is an AI player's turn.
- Apply a configurable think-time delay for natural pacing.
- Delegate move selection to AIEngine.
- Return the chosen pawn_id to the caller (state machine / WS router).
"""

from __future__ import annotations

import asyncio
import logging
import random

from app.game.ai_engine import AIEngine, AIPersona, GameSession

logger = logging.getLogger(__name__)

# Default think-time range (seconds) applied before the AI commits its move.
# Gives players the impression of a thinking opponent and smooths the UX.
# These values are used when the AIPersona does not carry its own timing.
_DEFAULT_THINK_MIN: float = 0.5
_DEFAULT_THINK_MAX: float = 1.0


class GameService:
    """Coordinates game turn logic, including server-side AI moves.

    Inject a custom ``AIEngine`` for testing or to swap strategy implementations
    without changing this class.
    """

    def __init__(self, ai_engine: AIEngine | None = None) -> None:
        self._ai_engine: AIEngine = ai_engine if ai_engine is not None else AIEngine()

    async def execute_ai_turn(
        self,
        game_session: GameSession,
        ai_persona: AIPersona,
    ) -> str:
        """Execute one AI turn and return the selected ``pawn_id``.

        Steps:
        1. Apply a short random delay so the AI appears to "think".
        2. Invoke ``AIEngine.select_move`` to choose from legal moves.
        3. Log the decision and return the pawn_id to the caller.

        AI players never send WebSocket messages — this method is their
        sole move-submission path.

        Args:
            game_session: Current game state including legal moves.
            ai_persona:   Configuration for this AI opponent (difficulty,
                          strategy weights, think time).

        Returns:
            The ``pawn_id`` string of the selected move.

        Raises:
            ValueError: if ``game_session.legal_moves`` is empty.
        """
        think_time = self._resolve_think_time(ai_persona)
        logger.debug(
            "AI '%s' thinking for %.2fs in room '%s' (roll=%d).",
            ai_persona.name,
            think_time,
            game_session.room_id,
            game_session.roll_value,
        )
        await asyncio.sleep(think_time)

        pawn_id = self._ai_engine.select_move(game_session, ai_persona)

        logger.info(
            "AI '%s' (difficulty=%s) committed pawn '%s' in room '%s' (roll=%d).",
            ai_persona.name,
            ai_persona.difficulty_level,
            pawn_id,
            game_session.room_id,
            game_session.roll_value,
        )
        return pawn_id

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_think_time(self, ai_persona: AIPersona) -> float:
        """Determine the think-time delay for this persona.

        Operators may embed ``think_time_min`` / ``think_time_max`` inside
        the JSONB ``strategy_weights`` column to customise timing per
        persona.  Falls back to module-level defaults otherwise.
        """
        weights = ai_persona.strategy_weights
        min_time = float(weights.get("think_time_min", _DEFAULT_THINK_MIN))
        max_time = float(weights.get("think_time_max", _DEFAULT_THINK_MAX))
        # Guard against invalid ranges coming from DB.
        if min_time > max_time:
            min_time, max_time = max_time, min_time
        return random.uniform(min_time, max_time)
