"""Cowrie-shell dice engine for Ashta Chamma (WO-012).

Four binary cowrie shells are thrown.  The number of face-up shells
determines the move value and extra-turn eligibility:

    Face-up count │ Move value │ Extra turn?
    ──────────────┼────────────┼────────────
         0        │  8 (Ashta) │   Yes
         1        │  1         │   Yes
         2        │  2         │   No
         3        │  3         │   No
         4        │  4 (Chamma)│   Yes

This matches the binomial distribution of four fair coins (p = 0.5) and
is identical to the legacy ``diceRoll()`` probability weights.

Design
------
``roll_cowries`` accepts an optional ``random.Random`` instance so callers
can inject a seeded generator for deterministic tests.  Production code
should pass ``None`` (default), which uses ``random.SystemRandom``
(CSPRNG-backed) for cryptographic fairness.
"""

from __future__ import annotations

import random
from typing import Optional

from app.game.board import EXTRA_TURN_ROLLS
from app.game.models import RollResult


def roll_cowries(rng: Optional[random.Random] = None) -> RollResult:
    """Simulate a single throw of four cowrie shells.

    Args:
        rng: A ``random.Random`` instance used for coin flips.  Pass a
             seeded ``random.Random(seed)`` in tests for reproducibility.
             Defaults to ``random.SystemRandom()`` for production use.

    Returns:
        A :class:`~app.game.models.RollResult` with the effective move
        value, individual shell states, and extra-turn flag.
    """
    _rng: random.Random = rng if rng is not None else random.SystemRandom()

    # Each cowrie is independently face-up (True) or face-down (False)
    cowries: list[bool] = [_rng.random() < 0.5 for _ in range(4)]
    up_count: int = sum(cowries)

    # 0 face-up → special value 8 (Ashta); otherwise equal to count
    value: int = 8 if up_count == 0 else up_count

    return RollResult(
        value=value,
        cowries=cowries,
        grants_extra_turn=value in EXTRA_TURN_ROLLS,
    )
