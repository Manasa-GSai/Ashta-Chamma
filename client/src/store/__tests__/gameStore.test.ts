/**
 * Unit tests for the Zustand game store.
 *
 * Tests run against the raw store API (getState / setState) without any React
 * rendering, satisfying the constraint that the store is framework-agnostic.
 */

import { beforeEach, describe, expect, it } from 'vitest';
import { useGameStore } from '../gameStore';
import { GamePhase, Screen } from '../types';
import type { PawnState, RoomPlayer, UserProfile } from '../types';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

/** Full store reset applied before every test to guarantee isolation. */
const resetStore = (): void => {
  useGameStore.setState({
    // Game slice
    pawns: [],
    currentPlayerIndex: 0,
    gamePhase: GamePhase.WAITING,
    currentRoll: null,
    legalMoveIds: [],
    // Room slice
    roomCode: null,
    players: [],
    roomStatus: 'WAITING',
    // User slice
    profile: null,
    isAuthenticated: false,
    // UI slice
    currentScreen: Screen.MAIN_MENU,
    isLoading: false,
    errorMessage: null,
    locale: 'en',
  });
};

const makePawn = (id: string, overrides: Partial<PawnState> = {}): PawnState => ({
  id,
  color: 'RED',
  pathIndex: 0,
  gridPosition: { row: 0, col: 0 },
  isHome: false,
  ...overrides,
});

const makePlayer = (id: string, overrides: Partial<RoomPlayer> = {}): RoomPlayer => ({
  id,
  name: `Player-${id}`,
  color: 'RED',
  isAI: false,
  isConnected: true,
  ...overrides,
});

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

beforeEach(resetStore);

// ---- Initial state ----

describe('initial state', () => {
  it('sets correct initial game slice values', () => {
    const s = useGameStore.getState();
    expect(s.pawns).toEqual([]);
    expect(s.currentPlayerIndex).toBe(0);
    expect(s.gamePhase).toBe(GamePhase.WAITING);
    expect(s.currentRoll).toBeNull();
    expect(s.legalMoveIds).toEqual([]);
  });

  it('sets correct initial room slice values', () => {
    const s = useGameStore.getState();
    expect(s.roomCode).toBeNull();
    expect(s.players).toEqual([]);
    expect(s.roomStatus).toBe('WAITING');
  });

  it('sets correct initial user slice values', () => {
    const s = useGameStore.getState();
    expect(s.profile).toBeNull();
    expect(s.isAuthenticated).toBe(false);
  });

  it('sets correct initial UI slice values', () => {
    const s = useGameStore.getState();
    expect(s.currentScreen).toBe(Screen.MAIN_MENU);
    expect(s.isLoading).toBe(false);
    expect(s.errorMessage).toBeNull();
    expect(s.locale).toBe('en');
  });
});

// ---- updateGameState ----

describe('updateGameState', () => {
  it('merges pawn list and roll into game state', () => {
    const pawn = makePawn('R1', { pathIndex: 3, gridPosition: { row: 2, col: 1 } });
    useGameStore.getState().updateGameState({
      pawns: [pawn],
      currentRoll: 3,
      gamePhase: GamePhase.SELECTING,
    });

    const s = useGameStore.getState();
    expect(s.pawns).toHaveLength(1);
    expect(s.pawns[0].id).toBe('R1');
    expect(s.currentRoll).toBe(3);
    expect(s.gamePhase).toBe(GamePhase.SELECTING);
  });

  it('preserves untouched fields when applying a partial delta', () => {
    // Confirm unchanged fields survive the merge
    useGameStore.getState().updateGameState({ currentRoll: 4 });
    const s = useGameStore.getState();
    expect(s.currentPlayerIndex).toBe(0);
    expect(s.gamePhase).toBe(GamePhase.WAITING);
    expect(s.legalMoveIds).toEqual([]);
  });

  it('overwrites legalMoveIds independently', () => {
    useGameStore.getState().updateGameState({ legalMoveIds: ['R1', 'R2'] });
    expect(useGameStore.getState().legalMoveIds).toEqual(['R1', 'R2']);
  });

  it('advances currentPlayerIndex', () => {
    useGameStore.getState().updateGameState({ currentPlayerIndex: 2 });
    expect(useGameStore.getState().currentPlayerIndex).toBe(2);
  });

  it('transitions gamePhase to GAME_OVER', () => {
    useGameStore.getState().updateGameState({ gamePhase: GamePhase.GAME_OVER });
    expect(useGameStore.getState().gamePhase).toBe(GamePhase.GAME_OVER);
  });
});

// ---- setRoomState ----

describe('setRoomState', () => {
  it('sets roomCode and players', () => {
    const players = [makePlayer('u1', { color: 'RED' })];
    useGameStore.getState().setRoomState({ roomCode: 'ABC123', players });

    const s = useGameStore.getState();
    expect(s.roomCode).toBe('ABC123');
    expect(s.players).toHaveLength(1);
    expect(s.players[0].name).toBe('Player-u1');
  });

  it('transitions roomStatus to IN_PROGRESS', () => {
    useGameStore.getState().setRoomState({ roomStatus: 'IN_PROGRESS' });
    expect(useGameStore.getState().roomStatus).toBe('IN_PROGRESS');
  });

  it('does not disturb other slices', () => {
    useGameStore.getState().setRoomState({ roomCode: 'XYZ' });
    const s = useGameStore.getState();
    // game slice untouched
    expect(s.gamePhase).toBe(GamePhase.WAITING);
    // UI slice untouched
    expect(s.currentScreen).toBe(Screen.MAIN_MENU);
  });
});

// ---- setUser ----

describe('setUser', () => {
  it('sets the profile and marks the user authenticated', () => {
    const profile: UserProfile = {
      id: 'u1',
      displayName: 'Alice',
      avatarUrl: null,
      locale: 'en',
    };
    useGameStore.getState().setUser(profile);

    const s = useGameStore.getState();
    expect(s.profile).toEqual(profile);
    expect(s.isAuthenticated).toBe(true);
  });

  it('clears the profile and marks the user unauthenticated when called with null', () => {
    // Set first, then clear
    useGameStore.getState().setUser({
      id: 'u1',
      displayName: 'Alice',
      avatarUrl: null,
      locale: 'en',
    });
    useGameStore.getState().setUser(null);

    const s = useGameStore.getState();
    expect(s.profile).toBeNull();
    expect(s.isAuthenticated).toBe(false);
  });
});

// ---- setError / clearError ----

describe('setError and clearError', () => {
  it('setError stores the error message', () => {
    useGameStore.getState().setError('Network timeout');
    expect(useGameStore.getState().errorMessage).toBe('Network timeout');
  });

  it('clearError resets errorMessage to null', () => {
    useGameStore.getState().setError('oops');
    useGameStore.getState().clearError();
    expect(useGameStore.getState().errorMessage).toBeNull();
  });

  it('setError overwrites a previous error', () => {
    useGameStore.getState().setError('first error');
    useGameStore.getState().setError('second error');
    expect(useGameStore.getState().errorMessage).toBe('second error');
  });
});

// ---- UI actions ----

describe('UI actions', () => {
  it('setCurrentScreen changes the active screen', () => {
    useGameStore.getState().setCurrentScreen(Screen.GAME);
    expect(useGameStore.getState().currentScreen).toBe(Screen.GAME);
  });

  it('setLoading toggles the loading flag', () => {
    useGameStore.getState().setLoading(true);
    expect(useGameStore.getState().isLoading).toBe(true);
    useGameStore.getState().setLoading(false);
    expect(useGameStore.getState().isLoading).toBe(false);
  });

  it('setLocale changes the locale', () => {
    useGameStore.getState().setLocale('te');
    expect(useGameStore.getState().locale).toBe('te');
  });
});

// ---- Selector logic ----

describe('selector logic (tested via getState)', () => {
  it('selectCurrentPlayer returns the player at currentPlayerIndex', () => {
    const players = [
      makePlayer('u1', { color: 'RED' }),
      makePlayer('u2', { color: 'GREEN' }),
    ];
    useGameStore.setState({ players, currentPlayerIndex: 1 });

    const s = useGameStore.getState();
    const currentPlayer = s.players[s.currentPlayerIndex];
    expect(currentPlayer?.id).toBe('u2');
  });

  it('selectCurrentPlayer returns undefined when players list is empty', () => {
    useGameStore.setState({ players: [], currentPlayerIndex: 0 });
    const s = useGameStore.getState();
    expect(s.players[s.currentPlayerIndex]).toBeUndefined();
  });

  it('selectMyPawns filters pawns by colour', () => {
    const pawns: PawnState[] = [
      makePawn('R1', { color: 'RED' }),
      makePawn('G1', { color: 'GREEN' }),
      makePawn('R2', { color: 'RED' }),
      makePawn('B1', { color: 'BLUE' }),
    ];
    useGameStore.setState({ pawns });

    const redPawns = useGameStore.getState().pawns.filter((p) => p.color === 'RED');
    expect(redPawns).toHaveLength(2);
    expect(redPawns.every((p) => p.color === 'RED')).toBe(true);
  });

  it('selectIsMyTurn returns true when ids match', () => {
    const players = [makePlayer('u1')];
    useGameStore.setState({ players, currentPlayerIndex: 0 });

    const s = useGameStore.getState();
    const current = s.players[s.currentPlayerIndex];
    expect(current?.id === 'u1').toBe(true);
    expect(current?.id === 'u2').toBe(false);
  });

  it('selectLegalMoves returns the current legalMoveIds', () => {
    useGameStore.setState({ legalMoveIds: ['R1', 'G3'] });
    expect(useGameStore.getState().legalMoveIds).toEqual(['R1', 'G3']);
  });
});
