import { create } from 'zustand';

/**
 * Represents the WebSocket connection lifecycle states exposed to the UI.
 * 'reconnecting' is distinct from 'connecting' so the UI can show retry context.
 */
export type ConnectionState = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

export interface RollResult {
  value: number;
  cowries: boolean[];
}

// Game state received from server — flexible shape for server-authoritative model.
export type GameState = Record<string, unknown>;

export interface GameStoreState {
  // --- Connection slice ---
  connectionState: ConnectionState;
  reconnectAttempts: number;
  connectionError: string | null;

  // --- Game state slice ---
  lastRollResult: RollResult | null;
  gameState: GameState | null;

  // --- Actions ---
  setConnectionState: (state: ConnectionState) => void;
  setReconnectAttempts: (attempts: number) => void;
  setConnectionError: (error: string | null) => void;
  updateRoll: (result: RollResult) => void;
  updateGameState: (state: GameState) => void;
  /**
   * Sets a user-visible error message (e.g. from server 'error' messages or
   * failed reconnection). Alias for setConnectionError — kept for semantic clarity.
   */
  setError: (error: string) => void;
  /**
   * Triggers a manual reconnection attempt via the registered callback from
   * WebSocketManager. Called by the UI "Reconnect" button after max retries.
   */
  triggerManualReconnect: () => void;
}

// Callback registered by WebSocketManager so the store action can reach it
// without creating a circular import. The manager calls setReconnectCallback
// on instantiation.
let _reconnectCallback: (() => void) | null = null;

export const setReconnectCallback = (cb: (() => void) | null): void => {
  _reconnectCallback = cb;
};

export const useGameStore = create<GameStoreState>((set) => ({
  connectionState: 'disconnected',
  reconnectAttempts: 0,
  connectionError: null,
  lastRollResult: null,
  gameState: null,

  setConnectionState: (state) => set({ connectionState: state }),
  setReconnectAttempts: (attempts) => set({ reconnectAttempts: attempts }),
  setConnectionError: (error) => set({ connectionError: error }),
  updateRoll: (result) => set({ lastRollResult: result }),
  updateGameState: (state) => set({ gameState: state }),
  setError: (error) => set({ connectionError: error }),

  triggerManualReconnect: () => {
    if (_reconnectCallback) {
      _reconnectCallback();
    }
  },
}));
