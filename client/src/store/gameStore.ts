import { create } from 'zustand';

export type GamePhase =
  | 'WAITING'
  | 'ROLLING'
  | 'SELECTING'
  | 'MOVING'
  | 'CAPTURING'
  | 'GAME_OVER';

/**
 * Represents a single legal move option returned by the server's move_options
 * message. Holds the pawn that may move and the board index it will land on.
 */
export interface MoveOption {
  pawn_id: number;
  target_pos: number;
}

export interface GameStore {
  gamePhase: GamePhase;
  currentPlayerId: string | null;
  localPlayerId: string | null;
  /** IDs of pawns that the current player may select this turn. */
  legalMoveIds: number[];
  /** Full move options including destination positions (for destination highlights). */
  moveOptions: MoveOption[];
  selectedPawnId: number | null;

  // --- Actions ---
  setGamePhase: (phase: GamePhase) => void;
  /**
   * Ingest move_options from the server, populate legalMoveIds, and
   * transition to the SELECTING phase so Pawn3D components become clickable.
   */
  setMoveOptions: (options: MoveOption[]) => void;
  setSelectedPawnId: (pawnId: number | null) => void;
  setCurrentPlayer: (playerId: string | null) => void;
  setLocalPlayer: (playerId: string | null) => void;
  /**
   * Clear all selection state once the player has chosen a pawn.
   * Called immediately after dispatching select_pawn so highlights disappear
   * and no further clicks are processed.
   */
  clearSelection: () => void;
}

export const useGameStore = create<GameStore>((set) => ({
  gamePhase: 'WAITING',
  currentPlayerId: null,
  localPlayerId: null,
  legalMoveIds: [],
  moveOptions: [],
  selectedPawnId: null,

  setGamePhase: (phase) => set({ gamePhase: phase }),

  setMoveOptions: (options) =>
    set({
      moveOptions: options,
      legalMoveIds: options.map((o) => o.pawn_id),
      gamePhase: 'SELECTING',
    }),

  setSelectedPawnId: (pawnId) => set({ selectedPawnId: pawnId }),

  setCurrentPlayer: (playerId) => set({ currentPlayerId: playerId }),

  setLocalPlayer: (playerId) => set({ localPlayerId: playerId }),

  clearSelection: () =>
    set({
      selectedPawnId: null,
      legalMoveIds: [],
      moveOptions: [],
    }),
}));
