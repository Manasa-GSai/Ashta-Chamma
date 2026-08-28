/**
 * Barrel export for the Zustand game store.
 *
 * Components should import from this path rather than from the individual
 * module files to insulate them from future internal reorganisation.
 */

export { useGameStore } from './gameStore';
export {
  useCurrentPlayer,
  useMyPawns,
  useIsMyTurn,
  useLegalMoves,
} from './selectors';
export { GamePhase, Screen } from './types';
export type {
  GameStore,
  GameState,
  GameStateActions,
  RoomState,
  RoomStateActions,
  UserState,
  UserStateActions,
  UIState,
  UIStateActions,
  PawnState,
  RoomPlayer,
  UserProfile,
  GridPosition,
  PlayerColor,
} from './types';
