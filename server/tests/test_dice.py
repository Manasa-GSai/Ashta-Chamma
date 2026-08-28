"""Tests for the cowrie shell roll engine (server/app/game/dice.py).

Coverage:
- All 5 possible roll values via deterministic shell configurations
- Extra-turn flag for every value
- Pawn-release flag for every value
- Statistical distribution matches the binomial(4, 0.5) expectation
- Seeded RNG produces reproducible results
- Configurable mouth-up probability (p parameter)
- Immutability of RollResult
- Invalid probability raises ValueError
"""

from __future__ import annotations

import random
from collections import Counter

import pytest

from app.game.dice import (
    EXTRA_TURN_VALUES,
    NUM_SHELLS,
    RELEASE_VALUES,
    RollResult,
    roll_cowries,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _forced_rng(mouth_up_count: int) -> random.Random:
    """Return a seeded RNG that will produce exactly *mouth_up_count* True
    values when ``random() < 0.5`` is evaluated NUM_SHELLS times in order.

    We rely on a search over seeds, which is acceptable in tests because
    the seed space is dense enough that matches are found immediately.
    """
    # Build a fake RNG subclass that returns a fixed sequence instead.
    # This avoids brittleness from seed-dependent ordering.
    class _FixedRNG(random.Random):
        def __init__(self, sequence: list[float]) -> None:
            super().__init__()
            self._seq = iter(sequence)

        def random(self) -> float:  # type: ignore[override]
            return next(self._seq)

    # mouth_up_count shells return 0.0 (< 0.5 → True)
    # remaining shells return 1.0 (>= 0.5 → False)
    floats = [0.0] * mouth_up_count + [1.0] * (NUM_SHELLS - mouth_up_count)
    return _FixedRNG(floats)


# ---------------------------------------------------------------------------
# Roll value mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("mouth_up_count", "expected_value"),
    [
        (0, 8),  # Ashta
        (1, 1),
        (2, 2),
        (3, 3),
        (4, 4),  # Chamma
    ],
)
def test_roll_value_mapping(mouth_up_count: int, expected_value: int) -> None:
    """Each count of mouth-up shells maps to the correct game value."""
    rng = _forced_rng(mouth_up_count)
    result = roll_cowries(rng=rng)
    assert result.value == expected_value


# ---------------------------------------------------------------------------
# individual_shells field
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("mouth_up_count", range(NUM_SHELLS + 1))
def test_individual_shells_length(mouth_up_count: int) -> None:
    """individual_shells always contains exactly 4 booleans."""
    rng = _forced_rng(mouth_up_count)
    result = roll_cowries(rng=rng)
    assert len(result.individual_shells) == NUM_SHELLS


@pytest.mark.parametrize("mouth_up_count", range(NUM_SHELLS + 1))
def test_individual_shells_count(mouth_up_count: int) -> None:
    """The number of True entries in individual_shells matches mouth_up_count."""
    rng = _forced_rng(mouth_up_count)
    result = roll_cowries(rng=rng)
    assert sum(result.individual_shells) == mouth_up_count


# ---------------------------------------------------------------------------
# Extra-turn flag
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("mouth_up_count", "expected_extra_turn"),
    [
        (0, True),   # value 8
        (1, True),   # value 1
        (2, False),  # value 2
        (3, False),  # value 3
        (4, True),   # value 4
    ],
)
def test_grants_extra_turn(mouth_up_count: int, expected_extra_turn: bool) -> None:
    rng = _forced_rng(mouth_up_count)
    result = roll_cowries(rng=rng)
    assert result.grants_extra_turn == expected_extra_turn


def test_extra_turn_values_constant() -> None:
    """EXTRA_TURN_VALUES contains exactly {1, 4, 8}."""
    assert EXTRA_TURN_VALUES == frozenset({1, 4, 8})


# ---------------------------------------------------------------------------
# Pawn-release flag
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    ("mouth_up_count", "expected_release"),
    [
        (0, True),   # value 8
        (1, True),   # value 1
        (2, False),  # value 2
        (3, False),  # value 3
        (4, False),  # value 4
    ],
)
def test_allows_pawn_release(mouth_up_count: int, expected_release: bool) -> None:
    rng = _forced_rng(mouth_up_count)
    result = roll_cowries(rng=rng)
    assert result.allows_pawn_release == expected_release


def test_release_values_constant() -> None:
    """RELEASE_VALUES contains exactly {1, 8}."""
    assert RELEASE_VALUES == frozenset({1, 8})


# ---------------------------------------------------------------------------
# Statistical distribution test (binomial(4, 0.5))
# ---------------------------------------------------------------------------

def test_statistical_distribution_within_tolerance() -> None:
    """Over 100,000 rolls the distribution should match binomial(4, 0.5)
    with each value within 2% of its theoretical frequency.

    Theoretical probabilities (C(4,k) / 16):
        value 1 (k=1): C(4,1)/16 = 4/16 = 25.00 %
        value 2 (k=2): C(4,2)/16 = 6/16 = 37.50 %
        value 3 (k=3): C(4,3)/16 = 4/16 = 25.00 %
        value 4 (k=4): C(4,4)/16 = 1/16 =  6.25 %
        value 8 (k=0): C(4,0)/16 = 1/16 =  6.25 %
    """
    n_rolls = 100_000
    tolerance = 0.02  # 2 percentage points

    theoretical: dict[int, float] = {
        1: 4 / 16,
        2: 6 / 16,
        3: 4 / 16,
        4: 1 / 16,
        8: 1 / 16,
    }

    rng = random.Random(42)
    counts: Counter[int] = Counter()
    for _ in range(n_rolls):
        counts[roll_cowries(rng=rng).value] += 1

    for value, expected_freq in theoretical.items():
        observed_freq = counts[value] / n_rolls
        assert abs(observed_freq - expected_freq) <= tolerance, (
            f"Value {value}: expected ~{expected_freq:.4f}, "
            f"got {observed_freq:.4f} (tolerance ±{tolerance})"
        )


# ---------------------------------------------------------------------------
# Determinism with seeded RNG
# ---------------------------------------------------------------------------

def test_seeded_rng_is_deterministic() -> None:
    """The same seed must produce the same sequence of rolls."""
    results_a = [roll_cowries(rng=random.Random(7)).value for _ in range(20)]
    results_b = [roll_cowries(rng=random.Random(7)).value for _ in range(20)]
    assert results_a == results_b


def test_different_seeds_produce_different_sequences() -> None:
    """Two different seeds should not produce identical 20-roll sequences
    (collision probability is negligible)."""
    results_a = [roll_cowries(rng=random.Random(1)).value for _ in range(20)]
    results_b = [roll_cowries(rng=random.Random(2)).value for _ in range(20)]
    assert results_a != results_b


# ---------------------------------------------------------------------------
# Configurable mouth-up probability
# ---------------------------------------------------------------------------

def test_p_zero_always_gives_ashta() -> None:
    """p=0 means all shells land mouth-down → value 8 every time."""
    rng = random.Random(0)
    for _ in range(20):
        result = roll_cowries(rng=rng, p=0.0)
        assert result.value == 8
        assert all(not s for s in result.individual_shells)


def test_p_one_always_gives_chamma() -> None:
    """p=1 means all shells land mouth-up → value 4 every time."""
    rng = random.Random(0)
    for _ in range(20):
        result = roll_cowries(rng=rng, p=1.0)
        assert result.value == 4
        assert all(result.individual_shells)


def test_invalid_p_raises_value_error() -> None:
    """p outside [0, 1] should raise ValueError."""
    with pytest.raises(ValueError, match="p must be in"):
        roll_cowries(p=-0.1)
    with pytest.raises(ValueError, match="p must be in"):
        roll_cowries(p=1.1)


# ---------------------------------------------------------------------------
# Immutability of RollResult
# ---------------------------------------------------------------------------

def test_roll_result_is_immutable() -> None:
    """RollResult is a frozen dataclass — attribute assignment must fail."""
    result = roll_cowries(rng=random.Random(0))
    with pytest.raises((AttributeError, TypeError)):
        result.value = 99  # type: ignore[misc]


def test_roll_result_is_dataclass_instance() -> None:
    result = roll_cowries(rng=random.Random(0))
    assert isinstance(result, RollResult)
