/**
 * Selector hooks for the Zustand game store.
 *
 * Each hook subscribes only to the slice of state it needs, so components
 * re-render only when the relevant data changes.  The hooks are thin wrappers
 * around `useGameStore` and contain no business logic.
 */

import { useGameStore } from './gameStore';
import type { PawnState, PlayerColor, RoomPlayer } from './types';

/**
 * selectCurrentPlayer — returns the RoomPlayer whose index matches
 * `currentPlayerIndex`.  Returns `undefined` during the lobby phase when
 * the players array may be shorter than expected.
 */
export const useCurrentPlayer = (): RoomPlayer | undefined =>
  useGameStore((state) => state.players[state.currentPlayerIndex]);

/**
 * selectMyPawns — returns all pawns that belong to `myColor`.
 * The component re-renders only when the pawns array changes, not on
 * every unrelated state update.
 */
export const useMyPawns = (myColor: PlayerColor): PawnState[] =>
  useGameStore((state) => state.pawns.filter((p) => p.color === myColor));

/**
 * selectIsMyTurn — returns true when the current player's id matches
 * `myPlayerId`.  Drives the interactive affordances in the HUD and pawn
 * selection overlay.
 */
export const useIsMyTurn = (myPlayerId: string): boolean =>
  useGameStore((state) => {
    const currentPlayer = state.players[state.currentPlayerIndex];
    return currentPlayer?.id === myPlayerId;
  });

/**
 * selectLegalMoves — returns the pawn IDs that may be moved with the
 * current roll.  The 3-D board uses this list to highlight selectable pawns.
 */
export const useLegalMoves = (): string[] =>
  useGameStore((state) => state.legalMoveIds);
