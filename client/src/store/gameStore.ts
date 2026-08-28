import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import {
  GamePhase,
  Screen,
  type GameState,
  type GameStore,
  type RoomState,
  type UserProfile,
  type UserState,
  type UIState,
} from './types';

// ---------------------------------------------------------------------------
// Default initial values for each slice
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

/**
 * useGameStore is the single Zustand store for all client state.
 *
 * It is organised into four logical slices:
 *   - Game   — board positions, current player, phase, roll, legal moves
 *   - Room   — room code, participant list, room lifecycle status
 *   - User   — authenticated user profile
 *   - UI     — active screen, loading flag, error message, locale
 *
 * The devtools middleware integrates with the Redux DevTools Extension for
 * time-travel debugging during development.
 */
export const useGameStore = create<GameStore>()(
  devtools(
    (set) => ({
      // ----- Game slice -----
      ...initialGameState,

      /**
       * Merge a partial state delta from the server into the game slice.
       * Only fields present in `delta` are overwritten; all other state is preserved.
       * Zustand performs a shallow top-level merge, so this is always immutable.
       */
      updateGameState: (delta: Partial<GameState>) =>
        set(delta as Partial<GameStore>, false, 'game/updateGameState'),

      // ----- Room slice -----
      ...initialRoomState,

      /**
       * Replace or merge room metadata received from the server (e.g. after a
       * join response or a player_joined WebSocket event).
       */
      setRoomState: (room: Partial<RoomState>) =>
        set(room as Partial<GameStore>, false, 'room/setRoomState'),

      // ----- User slice -----
      ...initialUserState,

      /**
       * Set the authenticated user's profile.
       * Passing null clears the profile and marks the user as unauthenticated,
       * which is used on logout or JWT expiry.
       */
      setUser: (profile: UserProfile | null) =>
        set(
          { profile, isAuthenticated: profile !== null },
          false,
          'user/setUser',
        ),

      // ----- UI slice -----
      ...initialUIState,

      setCurrentScreen: (screen) =>
        set({ currentScreen: screen }, false, 'ui/setCurrentScreen'),

      setLoading: (loading: boolean) =>
        set({ isLoading: loading }, false, 'ui/setLoading'),

      /** Show an error banner — typically triggered by a server error message. */
      setError: (message: string) =>
        set({ errorMessage: message }, false, 'ui/setError'),

      /** Dismiss the error banner once the user acknowledges it. */
      clearError: () =>
        set({ errorMessage: null }, false, 'ui/clearError'),

      setLocale: (locale: string) =>
        set({ locale }, false, 'ui/setLocale'),
    }),
    { name: 'AshtaChammaStore' },
  ),
);
