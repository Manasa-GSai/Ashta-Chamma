import { create } from 'zustand';
import type { PlayerColor } from '../utils/gridToWorld';

export interface GridPosition {
  row: number;
  col: number;
}

/**
 * Represents the full state of a single pawn.
 * pathIndex is -1 when the pawn has not yet entered the board.
 * gridPosition is null when the pawn is at home or finished.
 */
export interface PawnState {
  /** Unique identifier, e.g. "red_0", "blue_3" */
  id: string;
  color: PlayerColor;
  /** 0-3, the pawn's index within its player's set of 4 */
  pawnIndex: number;
  /**
   * Position in the player's path array.
   * -1 = at home base (not yet entered board).
   * 0-48 = on the board path.
   * 49 = finished (center square).
   */
  pathIndex: number;
  /** Current board grid position; null if at home */
  gridPosition: GridPosition | null;
  /** True when the pawn has not yet entered the board */
  isHome: boolean;
  /** True when the pawn has reached the center (won) */
  isFinished: boolean;
  /** True while the pawn is currently animating */
  isAnimating: boolean;
  /**
   * True when the pawn is returning to home after being captured.
   * Triggers a parabolic arc animation instead of a path-following animation.
   */
  captureReturn: boolean;
  /**
   * Intermediate path squares (excluding destination) for movement animation.
   * Empty for single-square moves or capture returns.
   */
  waypoints: GridPosition[];
}

interface GameStoreState {
  pawns: PawnState[];
  /** Replaces the entire pawn array (used for server state sync) */
  setPawns: (pawns: PawnState[]) => void;
  /** Marks a pawn's animation state (called by Pawn3D on completion) */
  setPawnAnimating: (id: string, isAnimating: boolean) => void;
  /**
   * Moves a pawn along waypoints to destination.
   * Sets isAnimating: true so Pawn3D triggers movement animation.
   */
  movePawn: (id: string, waypoints: GridPosition[], destination: GridPosition, newPathIndex: number) => void;
  /** Sends a captured pawn back to home base with arc animation */
  capturePawn: (id: string) => void;
  /** Marks a pawn as having finished (reached center square) */
  finishPawn: (id: string) => void;
}

/** All 16 pawns start at their home base positions */
const buildInitialPawns = (): PawnState[] =>
  (['red', 'blue', 'green', 'yellow'] as PlayerColor[]).flatMap((color) =>
    ([0, 1, 2, 3] as const).map<PawnState>((pawnIndex) => ({
      id: `${color}_${pawnIndex}`,
      color,
      pawnIndex,
      pathIndex: -1,
      gridPosition: null,
      isHome: true,
      isFinished: false,
      isAnimating: false,
      captureReturn: false,
      waypoints: [],
    })),
  );

export const useGameStore = create<GameStoreState>((set) => ({
  pawns: buildInitialPawns(),

  setPawns: (pawns) => set({ pawns }),

  setPawnAnimating: (id, isAnimating) =>
    set((state) => ({
      pawns: state.pawns.map((p) =>
        p.id === id
          ? { ...p, isAnimating, captureReturn: isAnimating ? p.captureReturn : false }
          : p,
      ),
    })),

  movePawn: (id, waypoints, destination, newPathIndex) =>
    set((state) => ({
      pawns: state.pawns.map((p) =>
        p.id === id
          ? {
              ...p,
              isHome: false,
              isAnimating: true,
              captureReturn: false,
              waypoints,
              gridPosition: destination,
              pathIndex: newPathIndex,
            }
          : p,
      ),
    })),

  capturePawn: (id) =>
    set((state) => ({
      pawns: state.pawns.map((p) =>
        p.id === id
          ? {
              ...p,
              pathIndex: -1,
              gridPosition: null,
              isHome: true,
              isAnimating: true,
              captureReturn: true,
              waypoints: [],
            }
          : p,
      ),
    })),

  finishPawn: (id) =>
    set((state) => ({
      pawns: state.pawns.map((p) =>
        p.id === id
          ? {
              ...p,
              isFinished: true,
              isAnimating: false,
              captureReturn: false,
              waypoints: [],
            }
          : p,
      ),
    })),
}));
