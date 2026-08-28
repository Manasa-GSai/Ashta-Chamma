/**
 * Zustand store for Ashta Chamma game state.
 *
 * Holds the authoritative client-side mirror of the server game state.
 * State is updated exclusively by applying server-sent WebSocket messages
 * so that the client never diverges from the server.
 *
 * The `isSpectator` flag drives conditional UI rendering: the Roll button
 * and pawn-selection are hidden for spectators.
 */

// NOTE: zustand is listed as a runtime dependency in the full project.
// The type imports below will resolve once `npm install` is run.
import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PlayerRole = 'player' | 'spectator';

export interface RoomPlayer {
  user_id: string;
  display_name: string;
  role: PlayerRole;
  player_index: number | null;
  color: string | null;
}

export type RoomStatus = 'waiting' | 'in_progress' | 'completed' | 'abandoned';

export interface RoomState {
  code: string;
  host_user_id: string;
  status: RoomStatus;
  max_players: number;
  players: RoomPlayer[];
}

export interface GamePhase {
  currentTurn: string | null;
  rollResult: number | null;
  moveOptions: Array<{ pawn_id: number; target_pos: number }>;
}

// Shape of the server's `state_update` WebSocket message
export interface StateUpdateMessage {
  type: 'state_update';
  state: RoomState;
  is_spectator?: boolean;
}

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

interface GameStore {
  // Room identity
  room: RoomState | null;
  /** True when the current user joined as a spectator. */
  isSpectator: boolean;
  currentUserId: string | null;

  // Live game phase
  phase: GamePhase;

  // Actions
  setCurrentUserId: (userId: string) => void;
  setIsSpectator: (value: boolean) => void;
  setRoom: (room: RoomState) => void;
  setRollResult: (value: number | null) => void;
  setCurrentTurn: (userId: string | null) => void;
  setMoveOptions: (options: Array<{ pawn_id: number; target_pos: number }>) => void;

  /**
   * Apply a `state_update` message from the server.
   * Updates room snapshot and spectator flag atomically.
   */
  applyStateUpdate: (message: StateUpdateMessage) => void;

  /** Reset store to initial values (e.g. after leaving a room). */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Initial values
// ---------------------------------------------------------------------------

const initialPhase: GamePhase = {
  currentTurn: null,
  rollResult: null,
  moveOptions: [],
};

const initialState = {
  room: null,
  isSpectator: false,
  currentUserId: null,
  phase: initialPhase,
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useGameStore = create<GameStore>((set) => ({
  ...initialState,

  setCurrentUserId: (currentUserId: string) => set({ currentUserId }),

  setIsSpectator: (isSpectator: boolean) => set({ isSpectator }),

  setRoom: (room: RoomState) => set({ room }),

  setRollResult: (rollResult: number | null) =>
    set((prev) => ({ phase: { ...prev.phase, rollResult } })),

  setCurrentTurn: (currentTurn: string | null) =>
    set((prev) => ({ phase: { ...prev.phase, currentTurn } })),

  setMoveOptions: (moveOptions: Array<{ pawn_id: number; target_pos: number }>) =>
    set((prev) => ({ phase: { ...prev.phase, moveOptions } })),

  applyStateUpdate: (message: StateUpdateMessage) =>
    set((prev) => ({
      room: message.state,
      // Only update isSpectator when the server explicitly sends the flag;
      // subsequent state_update messages after the initial one omit it.
      isSpectator:
        message.is_spectator !== undefined ? message.is_spectator : prev.isSpectator,
    })),

  reset: () => set({ ...initialState, phase: { ...initialPhase } }),
}));
