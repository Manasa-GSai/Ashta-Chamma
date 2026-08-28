"""Cowrie shell roll engine for Ashta Chamma.

Each cowrie shell is modelled as an independent Bernoulli trial with
mouth-up probability *p* (default 0.5). The number of mouth-up faces
determines the roll value according to the traditional mapping:

    0 mouth-up → 8  (Ashta)
    1 mouth-up → 1
    2 mouth-up → 2
    3 mouth-up → 3
    4 mouth-up → 4  (Chamma)

Values 1, 4, and 8 grant an extra turn; values 1 and 8 also allow
releasing a new pawn from the home square. This module is purely
functional — no side effects, no I/O — so it can be called safely from
the game state machine or tested in isolation.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Module-level rule constants — consumers should reference these instead of
# hardcoding the sets, keeping rule changes localised to one place.
# ---------------------------------------------------------------------------
EXTRA_TURN_VALUES: frozenset[int] = frozenset({1, 4, 8})
RELEASE_VALUES: frozenset[int] = frozenset({1, 8})

# Maps the count of mouth-up shells to the corresponding game value.
# 0 mouth-up is the special "Ashta" (8) outcome.
_MOUTH_UP_TO_VALUE: dict[int, int] = {0: 8, 1: 1, 2: 2, 3: 3, 4: 4}

NUM_SHELLS: int = 4


@dataclass(frozen=True)
class RollResult:
    """Immutable result of a single cowrie shell roll.

    Attributes:
        value: Game value derived from the roll (1, 2, 3, 4, or 8).
        individual_shells: Ordered list of per-shell outcomes
            (True = mouth-up, False = mouth-down). Always length 4.
        grants_extra_turn: True when the player is entitled to another turn
            (values 1, 4, and 8).
        allows_pawn_release: True when the player may release a pawn from
            the home square (values 1 and 8).
    """

    value: int
    individual_shells: list[bool]
    grants_extra_turn: bool
    allows_pawn_release: bool


def roll_cowries(
    rng: random.Random | None = None,
    *,
    p: float = 0.5,
) -> RollResult:
    """Simulate a roll of 4 cowrie shells and return a typed result.

    Each shell is an independent Bernoulli trial with mouth-up probability
    *p* (default 0.5, representing a fair shell). Inject a seeded
    :class:`random.Random` instance via *rng* for deterministic tests.

    Args:
        rng: Optional :class:`random.Random` instance. When *None* the
             module-level random generator is used (non-deterministic).
        p:   Probability that a single shell lands mouth-up. Must be in
             [0, 1].

    Returns:
        A frozen :class:`RollResult` describing the outcome.

    Raises:
        ValueError: If *p* is not in the range [0, 1].
    """
    if not 0.0 <= p <= 1.0:
        raise ValueError(f"p must be in [0, 1], got {p!r}")

    # Use the injected RNG when available, otherwise fall back to the
    # module-level random functions (backed by os.urandom on first use).
    rand_float = rng.random if rng is not None else random.random

    shells: list[bool] = [rand_float() < p for _ in range(NUM_SHELLS)]
    mouth_up_count: int = sum(shells)
    value: int = _MOUTH_UP_TO_VALUE[mouth_up_count]

    return RollResult(
        value=value,
        individual_shells=shells,
        grants_extra_turn=value in EXTRA_TURN_VALUES,
        allows_pawn_release=value in RELEASE_VALUES,
    )
