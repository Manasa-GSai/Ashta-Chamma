"""Move validation for Ashta Chamma.

All move-computation logic lives here.  This module is deliberately free of
I/O and state mutations — it receives immutable snapshots and returns a list
of legal :class:`Move` objects.

Rules enforced:
  1. A pawn at home (path index 0) can only move on a roll of 1 or 8.
  2. A pawn that has already reached the centre (path index WIN_PATH_INDEX)
     is finished and cannot move again.
  3. A pawn cannot overshoot the final centre square.
  4. A pawn cannot land on a square already occupied by a friendly pawn
     unless that square is a safe square (safe squares allow stacking).
"""

from __future__ import annotations

from dataclasses import dataclass

from .board import PATHS, SAFE_SQUARES, WIN_PATH_INDEX
from .dice import RELEASE_VALUES


@dataclass(frozen=True)
class Move:
    """A validated move for a single pawn.

    Attributes:
        player_index: The player who owns this pawn (0–3).
        pawn_index: Which of the player's four pawns is moving (0–3).
        from_path_index: Current position in ``PATHS[player_index]``.
        to_path_index: Destination position in ``PATHS[player_index]``.
    """

    player_index: int
    pawn_index: int
    from_path_index: int
    to_path_index: int

    @property
    def is_release(self) -> bool:
        """True when this move releases a pawn from its home base."""
        return self.from_path_index == 0

    @property
    def is_winning(self) -> bool:
        """True when this move lands the pawn on the centre square."""
        return self.to_path_index == WIN_PATH_INDEX


def compute_legal_moves(
    player: int,
    pawn_path_indices: tuple[int, ...],
    all_pawn_positions: tuple[tuple[int, ...], ...],
    roll: int,
) -> list[Move]:
    """Return all legal moves for *player* given a cowrie *roll*.

    Args:
        player: Index of the current player (0–3).
        pawn_path_indices: Path indices for each of the player's 4 pawns.
            Index 0 means "at home" (not in play); WIN_PATH_INDEX means
            the pawn has already won.
        all_pawn_positions: Path indices for all 4 players' pawns, indexed
            as ``all_pawn_positions[player][pawn]``.  Used to detect
            friendly-pawn blocking.
        roll: The cowrie roll value (1, 2, 3, 4, or 8).

    Returns:
        A (possibly empty) list of :class:`Move` objects.  An empty list
        means the player's turn passes without moving.
    """
    path = PATHS[player]
    moves: list[Move] = []

    for pawn_idx, current_idx in enumerate(pawn_path_indices):
        # Already at centre — this pawn is done.
        if current_idx == WIN_PATH_INDEX:
            continue

        # Pawn is at home and the roll does not allow release.
        if current_idx == 0 and roll not in RELEASE_VALUES:
            continue

        target_idx = current_idx + roll

        # Cannot overshoot the final square.
        if target_idx > WIN_PATH_INDEX:
            continue

        target_sq = path[target_idx]

        # Check whether a friendly pawn already occupies the target square.
        # Friendly stacking is permitted only on safe squares.
        if target_sq not in SAFE_SQUARES:
            blocked = False
            for other_idx, other_path_idx in enumerate(pawn_path_indices):
                if other_idx == pawn_idx:
                    continue
                # Pawns at home or already won don't block the outer track.
                if other_path_idx == 0 or other_path_idx == WIN_PATH_INDEX:
                    continue
                if path[other_path_idx] == target_sq:
                    blocked = True
                    break
            if blocked:
                continue

        moves.append(
            Move(
                player_index=player,
                pawn_index=pawn_idx,
                from_path_index=current_idx,
                to_path_index=target_idx,
            )
        )

    return moves
