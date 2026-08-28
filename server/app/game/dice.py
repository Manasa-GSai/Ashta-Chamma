"""Cowrie roll engine for Ashta Chamma.

In the physical game four cowrie shells are thrown. The number of shells
landing face-up determines the move value:

    face-up count → value → extra turn → can release pawn from home
    0             → 8      → True       → True   (Ashta)
    1             → 1      → True       → True
    2             → 2      → False      → False
    3             → 3      → False      → False
    4             → 4      → True       → False  (Chamma)

The ``roll_cowries`` function accepts an optional ``random.Random`` instance so
that tests can inject a seeded generator for deterministic sequences.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Final

# ---------------------------------------------------------------------------
# Roll constants
# ---------------------------------------------------------------------------

# Possible roll values.
COWRIE_VALUES: Final[tuple[int, ...]] = (1, 2, 3, 4, 8)

# Roll values that grant the current player an extra turn.
EXTRA_TURN_VALUES: Final[frozenset[int]] = frozenset({1, 4, 8})

# Roll values that allow a new pawn to be released from its home base.
RELEASE_VALUES: Final[frozenset[int]] = frozenset({1, 8})

# ---------------------------------------------------------------------------
# Cowrie mapping: face-up count → move value
# ---------------------------------------------------------------------------

_FACE_UP_TO_VALUE: Final[dict[int, int]] = {
    0: 8,
    1: 1,
    2: 2,
    3: 3,
    4: 4,
}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CowrieRoll:
    """Immutable result of a single cowrie throw.

    Attributes:
        value: The move value (1, 2, 3, 4, or 8).
        extra_turn: Whether the current player rolls again after moving.
        can_release: Whether a pawn may be released from home this turn.
        cowries_face_up: Raw count of cowries that landed face-up (0–4).
    """

    value: int
    extra_turn: bool
    can_release: bool
    cowries_face_up: int


# ---------------------------------------------------------------------------
# Roll function
# ---------------------------------------------------------------------------


def roll_cowries(rng: random.Random | None = None) -> CowrieRoll:
    """Simulate throwing four cowrie shells.

    Each shell independently lands face-up with probability 0.5.  The count
    of face-up shells maps to a move value and determines turn-continuation
    flags.

    Args:
        rng: Optional seeded ``random.Random`` instance.  When ``None`` a
             fresh ``random.SystemRandom()`` is used for cryptographic
             fairness.  Pass a seeded instance in tests for determinism.

    Returns:
        A :class:`CowrieRoll` describing the outcome.
    """
    r: random.Random | random.SystemRandom = rng if rng is not None else random.SystemRandom()
    face_up = sum(r.randint(0, 1) for _ in range(4))
    value = _FACE_UP_TO_VALUE[face_up]
    return CowrieRoll(
        value=value,
        extra_turn=value in EXTRA_TURN_VALUES,
        can_release=value in RELEASE_VALUES,
        cowries_face_up=face_up,
    )


def make_roll(value: int) -> CowrieRoll:
    """Construct a :class:`CowrieRoll` directly from a known value.

    Useful in tests when you want to control the exact roll without mocking
    the RNG.  Raises ``ValueError`` for an invalid value.
    """
    if value not in set(COWRIE_VALUES):
        raise ValueError(f"Invalid cowrie roll value: {value!r}.  Must be one of {COWRIE_VALUES}.")
    # Invert the face-up mapping for the cowries_face_up field.
    face_up = next(k for k, v in _FACE_UP_TO_VALUE.items() if v == value)
    return CowrieRoll(
        value=value,
        extra_turn=value in EXTRA_TURN_VALUES,
        can_release=value in RELEASE_VALUES,
        cowries_face_up=face_up,
    )
