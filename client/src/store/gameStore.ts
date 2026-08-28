import { create } from 'zustand';

export type GamePhase = 'WAITING' | 'ROLLING' | 'SELECTING' | 'MOVING' | 'GAME_OVER';

export interface GameState {
  currentPlayer: number;
  rollResult: number | null;
  phase: GamePhase;
  players: string[];
  boardState: Record<string, number>;
  setCurrentPlayer: (player: number) => void;
  setRollResult: (result: number | null) => void;
  setPhase: (phase: GamePhase) => void;
  resetGame: () => void;
}

const initialState = {
  currentPlayer: 0,
  rollResult: null,
  phase: 'WAITING' as GamePhase,
  players: [],
  boardState: {},
};

export const useGameStore = create<GameState>((set) => ({
  ...initialState,
  setCurrentPlayer: (player) => set({ currentPlayer: player }),
  setRollResult: (result) => set({ rollResult: result }),
  setPhase: (phase) => set({ phase }),
  resetGame: () => set(initialState),
}));
