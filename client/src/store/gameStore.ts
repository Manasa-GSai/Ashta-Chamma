import { create } from 'zustand';

export interface Player {
  id: string;
  name: string;
  color: string;
  playerIndex: number;
  isConnected: boolean;
  isAI: boolean;
}

export type GamePhase = 'waiting' | 'rolling' | 'selecting' | 'moving' | 'game_over';

interface GameStore {
  roomCode: string | null;
  players: Player[];
  currentPlayerIndex: number;
  lastRollResult: number | null;
  phase: GamePhase;

  setRoomCode: (code: string | null) => void;
  setPlayers: (players: Player[]) => void;
  setCurrentPlayerIndex: (index: number) => void;
  setLastRollResult: (result: number | null) => void;
  setPhase: (phase: GamePhase) => void;
  reset: () => void;
}

const initialState: Pick<
  GameStore,
  'roomCode' | 'players' | 'currentPlayerIndex' | 'lastRollResult' | 'phase'
> = {
  roomCode: null,
  players: [],
  currentPlayerIndex: 0,
  lastRollResult: null,
  phase: 'waiting',
};

export const useGameStore = create<GameStore>()((set) => ({
  ...initialState,
  setRoomCode: (code) => set({ roomCode: code }),
  setPlayers: (players) => set({ players }),
  setCurrentPlayerIndex: (index) => set({ currentPlayerIndex: index }),
  setLastRollResult: (result) => set({ lastRollResult: result }),
  setPhase: (phase) => set({ phase }),
  reset: () => set(initialState),
}));
