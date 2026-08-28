// All TypeScript interfaces and enums for the Zustand game store.
// These types mirror the server-side game state so the client can
// synchronise with server-sent state deltas without data transformation.

/** 2-D grid coordinate used to position a pawn on the rendered board. */
export interface GridPosition {
  row: number;
  col: number;
}

/** The four player colours supported by Ashta Chamma. */
export type PlayerColor = 'RED' | 'GREEN' | 'YELLOW' | 'BLUE';

/**
 * GamePhase mirrors the server-side FSM states.
 * The client only reads this value — it never transitions state directly.
 */
export enum GamePhase {
  WAITING = 'WAITING',
  ROLLING = 'ROLLING',
  SELECTING = 'SELECTING',
  MOVING = 'MOVING',
  CAPTURING = 'CAPTURING',
  GAME_OVER = 'GAME_OVER',
}

/**
 * Screen controls which top-level UI view is currently visible.
 * Transitions are driven by server events and user navigation.
 */
export enum Screen {
  MAIN_MENU = 'MAIN_MENU',
  LOBBY = 'LOBBY',
  GAME = 'GAME',
  RULES = 'RULES',
}

/** Per-pawn data mirrored from the server board snapshot. */
export interface PawnState {
  /** Unique pawn identifier, e.g. "R1"–"R4", "G1"–"G4". */
  id: string;
  color: PlayerColor;
  /**
   * Position along the shared path (0-based).
   * -1 means the pawn is still in its home base and has not entered the board.
   */
  pathIndex: number;
  /** Rendered grid cell for the 3-D board visualisation. */
  gridPosition: GridPosition;
  /** True once the pawn has reached its final home cell and is off the board. */
  isHome: boolean;
}

/** One participant in a game room — either a human player or an AI persona. */
export interface RoomPlayer {
  id: string;
  name: string;
  color: PlayerColor;
  isAI: boolean;
  isConnected: boolean;
}

/** Registered user profile returned by the /api/users/me endpoint. */
export interface UserProfile {
  id: string;
  displayName: string;
  avatarUrl: string | null;
  locale: string;
}

// ---------------------------------------------------------------------------
// State slice interfaces
// ---------------------------------------------------------------------------

/** The board-level slice — everything needed to render the game in progress. */
export interface GameState {
  /** All 16 pawns (4 per player). Empty array before a game starts. */
  pawns: PawnState[];
  /** Index into the `players` array indicating whose turn it is. */
  currentPlayerIndex: number;
  gamePhase: GamePhase;
  /** The numeric result of the most recent cowrie roll, or null if not yet rolled. */
  currentRoll: number | null;
  /** Pawn IDs that may legally be moved with the current roll. */
  legalMoveIds: string[];
}

/** Actions for the game slice. */
export interface GameStateActions {
  /**
   * Merge a partial server-sent delta into the current game state.
   * Only the fields present in `delta` are updated; others are preserved.
   */
  updateGameState: (delta: Partial<GameState>) => void;
}

/** Room-level slice — lobby metadata and participant list. */
export interface RoomState {
  roomCode: string | null;
  players: RoomPlayer[];
  roomStatus: 'WAITING' | 'IN_PROGRESS' | 'COMPLETED' | 'ABANDONED';
}

/** Actions for the room slice. */
export interface RoomStateActions {
  setRoomState: (room: Partial<RoomState>) => void;
}

/** Authentication / profile slice. */
export interface UserState {
  profile: UserProfile | null;
  isAuthenticated: boolean;
}

/** Actions for the user slice. */
export interface UserStateActions {
  /** Sets the user profile and derives `isAuthenticated` from whether it is non-null. */
  setUser: (profile: UserProfile | null) => void;
}

/** UI-only slice — screen visibility, loading spinners, error banners, locale. */
export interface UIState {
  currentScreen: Screen;
  isLoading: boolean;
  errorMessage: string | null;
  locale: string;
}

/** Actions for the UI slice. */
export interface UIStateActions {
  setCurrentScreen: (screen: Screen) => void;
  setLoading: (loading: boolean) => void;
  /** Display an error banner with the provided message. */
  setError: (message: string) => void;
  /** Dismiss the current error banner. */
  clearError: () => void;
  /** Switch the active locale (e.g. "en", "te", "hi"). */
  setLocale: (locale: string) => void;
}

// ---------------------------------------------------------------------------
// Combined store type
// ---------------------------------------------------------------------------

/**
 * GameStore is the full shape of the Zustand store — all slices combined.
 * Exported so that components and selectors can reference it without
 * importing from the store module (avoiding circular deps).
 */
export type GameStore = GameState &
  GameStateActions &
  RoomState &
  RoomStateActions &
  UserState &
  UserStateActions &
  UIState &
  UIStateActions;
