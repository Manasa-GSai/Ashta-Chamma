import { create } from 'zustand';
import type {
  GameState,
  RoomState,
  UserState,
  UIState,
  GameStore,
  RoomPlayer,
} from './types';
import { GamePhase, Screen } from './types';

// Re-export so consumers that import from this module continue to work.
export type { GameState, GameStore };
export type { RoomPlayer as Player };
export { GamePhase, Screen };

// ---------------------------------------------------------------------------
// Chat slice types
// ---------------------------------------------------------------------------

export interface ChatMessage {
  id: string;
  senderName: string;
  /** CSS-compatible colour string matching the player's board colour. */
  senderColor: string;
  text: string;
  /** ISO-8601 timestamp string. */
  timestamp: string;
}

export const MAX_CHAT_MESSAGES = 100;

// ---------------------------------------------------------------------------
// Connection slice types
// ---------------------------------------------------------------------------

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'reconnecting';

export interface RollResult {
  /** Numeric game value of the roll (0–4 for cowrie shells). */
  value: number;
  /** True = mouth-up for each shell in throw order. */
  cowries: boolean[];
}

// ---------------------------------------------------------------------------
// Move-option type (destination highlights on the board)
// ---------------------------------------------------------------------------

export interface MoveOption {
  pawn_id: string;
  target_pos: number;
}

// ---------------------------------------------------------------------------
// Reconnect callback bridge
// WebSocketManager registers a callback here so the UI button can trigger
// reconnection without importing the manager directly.
// ---------------------------------------------------------------------------

let _reconnectCallback: (() => void) | null = null;

export const setReconnectCallback = (cb: (() => void) | null): void => {
  _reconnectCallback = cb;
};

// ---------------------------------------------------------------------------
// Full store shape = GameStore (from types.ts) + Chat + Connection + extras
// ---------------------------------------------------------------------------

type FullStore = GameStore & {
  // Extra game actions not captured in GameStateActions
  clearSelection: () => void;
  setGamePhase: (phase: GamePhase) => void;
  updateRoll: (roll: RollResult) => void;
  setMoveOptions: (options: MoveOption[]) => void;
  moveOptions: MoveOption[];

  // Chat slice
  chatMessages: ChatMessage[];
  isChatOpen: boolean;
  addChatMessage: (msg: ChatMessage) => void;
  toggleChat: () => void;

  // Connection slice
  connectionState: ConnectionState;
  reconnectAttempts: number;
  connectionError: string | null;
  setConnectionState: (state: ConnectionState) => void;
  setConnectionError: (error: string | null) => void;
  setReconnectAttempts: (attempts: number) => void;
  triggerManualReconnect: () => void;
};

// ---------------------------------------------------------------------------
// Initial state slices
// ---------------------------------------------------------------------------

const initialGameState: GameState = {
  pawns: [],
  currentPlayerIndex: 0,
  gamePhase: GamePhase.WAITING,
  currentRoll: null,
  legalMoveIds: [],
};

const initialRoomState: RoomState = {
  roomCode: null,
  players: [],
  roomStatus: 'WAITING',
};

const initialUserState: UserState = {
  profile: null,
  isAuthenticated: false,
};

const initialUIState: UIState = {
  currentScreen: Screen.MAIN_MENU,
  isLoading: false,
  errorMessage: null,
  locale: 'en',
};

// ---------------------------------------------------------------------------
// Store
// ---------------------------------------------------------------------------

export const useGameStore = create<FullStore>((set) => ({
  // ---- Game slice ----
  ...initialGameState,
  updateGameState: (delta) => set((s) => ({ ...s, ...delta })),
  clearSelection: () => set({ legalMoveIds: [], moveOptions: [] }),
  setGamePhase: (phase) => set({ gamePhase: phase }),
  updateRoll: (roll) => set({ currentRoll: roll.value }),
  /**
   * Populates both moveOptions (destination highlights) and legalMoveIds
   * (which pawns are selectable) from a single server payload.
   */
  setMoveOptions: (options) =>
    set({ moveOptions: options, legalMoveIds: options.map((o) => o.pawn_id) }),
  moveOptions: [],

  // ---- Room slice ----
  ...initialRoomState,
  setRoomState: (room) => set((s) => ({ ...s, ...room })),

  // ---- User slice ----
  ...initialUserState,
  setUser: (profile) => set({ profile, isAuthenticated: profile !== null }),

  // ---- UI slice ----
  ...initialUIState,
  setCurrentScreen: (screen) => set({ currentScreen: screen }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (message) => set({ errorMessage: message }),
  clearError: () => set({ errorMessage: null }),
  setLocale: (locale) => set({ locale }),

  // ---- Chat slice ----
  chatMessages: [],
  isChatOpen: false,
  addChatMessage: (msg) =>
    set((s) => ({
      chatMessages:
        s.chatMessages.length >= MAX_CHAT_MESSAGES
          ? [...s.chatMessages.slice(1), msg]
          : [...s.chatMessages, msg],
    })),
  toggleChat: () => set((s) => ({ isChatOpen: !s.isChatOpen })),

  // ---- Connection slice ----
  connectionState: 'disconnected' as ConnectionState,
  reconnectAttempts: 0,
  connectionError: null,
  setConnectionState: (state) => set({ connectionState: state }),
  setConnectionError: (error) => set({ connectionError: error }),
  setReconnectAttempts: (attempts) => set({ reconnectAttempts: attempts }),
  triggerManualReconnect: () => {
    if (_reconnectCallback) {
      _reconnectCallback();
    }
  },
}));
