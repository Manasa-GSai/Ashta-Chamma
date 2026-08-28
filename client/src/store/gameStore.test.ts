import { describe, it, expect, beforeEach } from 'vitest';
import { useGameStore } from './gameStore';
import type { MoveOption } from './gameStore';

/**
 * Reset the store to a clean initial state before each test so that tests
 * do not bleed state into one another.
 */
const resetStore = () =>
  useGameStore.setState({
    gamePhase: 'WAITING',
    currentPlayerId: null,
    localPlayerId: null,
    legalMoveIds: [],
    moveOptions: [],
    selectedPawnId: null,
  });

describe('gameStore', () => {
  beforeEach(resetStore);

  // -------------------------------------------------------------------------
  // Initial state
  // -------------------------------------------------------------------------

  it('has WAITING phase and empty legal move list by default', () => {
    const state = useGameStore.getState();
    expect(state.gamePhase).toBe('WAITING');
    expect(state.legalMoveIds).toHaveLength(0);
    expect(state.moveOptions).toHaveLength(0);
    expect(state.selectedPawnId).toBeNull();
  });

  // -------------------------------------------------------------------------
  // setMoveOptions — AC1 + AC4 setup
  // -------------------------------------------------------------------------

  it('setMoveOptions transitions to SELECTING phase', () => {
    const options: MoveOption[] = [{ pawn_id: 1, target_pos: 5 }];
    useGameStore.getState().setMoveOptions(options);
    expect(useGameStore.getState().gamePhase).toBe('SELECTING');
  });

  it('setMoveOptions populates legalMoveIds from pawn_id fields', () => {
    const options: MoveOption[] = [
      { pawn_id: 1, target_pos: 5 },
      { pawn_id: 3, target_pos: 12 },
    ];
    useGameStore.getState().setMoveOptions(options);
    const { legalMoveIds } = useGameStore.getState();
    expect(legalMoveIds).toContain(1);
    expect(legalMoveIds).toContain(3);
    expect(legalMoveIds).toHaveLength(2);
  });

  it('setMoveOptions stores the full move options array', () => {
    const options: MoveOption[] = [{ pawn_id: 2, target_pos: 8 }];
    useGameStore.getState().setMoveOptions(options);
    expect(useGameStore.getState().moveOptions).toEqual(options);
  });

  it('setMoveOptions with empty array leaves legalMoveIds empty', () => {
    useGameStore.getState().setMoveOptions([]);
    expect(useGameStore.getState().legalMoveIds).toHaveLength(0);
    // Phase still transitions to SELECTING even without moves (server sends 0
    // options when the player must pass; this is consistent with the FSM).
    expect(useGameStore.getState().gamePhase).toBe('SELECTING');
  });

  // -------------------------------------------------------------------------
  // clearSelection — AC6 setup
  // -------------------------------------------------------------------------

  it('clearSelection empties legalMoveIds and moveOptions', () => {
    useGameStore.getState().setMoveOptions([{ pawn_id: 1, target_pos: 3 }]);
    useGameStore.getState().clearSelection();
    const state = useGameStore.getState();
    expect(state.legalMoveIds).toHaveLength(0);
    expect(state.moveOptions).toHaveLength(0);
  });

  it('clearSelection resets selectedPawnId to null', () => {
    useGameStore.getState().setMoveOptions([{ pawn_id: 1, target_pos: 3 }]);
    useGameStore.getState().setSelectedPawnId(1);
    useGameStore.getState().clearSelection();
    expect(useGameStore.getState().selectedPawnId).toBeNull();
  });

  it('clearSelection does not change the gamePhase', () => {
    // Phase is controlled separately (e.g. setGamePhase('MOVING') on selection).
    useGameStore.getState().setMoveOptions([{ pawn_id: 1, target_pos: 3 }]);
    useGameStore.getState().setGamePhase('MOVING');
    useGameStore.getState().clearSelection();
    expect(useGameStore.getState().gamePhase).toBe('MOVING');
  });

  // -------------------------------------------------------------------------
  // setGamePhase
  // -------------------------------------------------------------------------

  it('setGamePhase updates the phase to the supplied value', () => {
    useGameStore.getState().setGamePhase('ROLLING');
    expect(useGameStore.getState().gamePhase).toBe('ROLLING');
    useGameStore.getState().setGamePhase('MOVING');
    expect(useGameStore.getState().gamePhase).toBe('MOVING');
  });

  // -------------------------------------------------------------------------
  // setSelectedPawnId
  // -------------------------------------------------------------------------

  it('setSelectedPawnId stores the pawn id', () => {
    useGameStore.getState().setSelectedPawnId(42);
    expect(useGameStore.getState().selectedPawnId).toBe(42);
  });

  // -------------------------------------------------------------------------
  // Player identity helpers
  // -------------------------------------------------------------------------

  it('setCurrentPlayer and setLocalPlayer update the respective IDs', () => {
    useGameStore.getState().setCurrentPlayer('player-1');
    useGameStore.getState().setLocalPlayer('player-2');
    const state = useGameStore.getState();
    expect(state.currentPlayerId).toBe('player-1');
    expect(state.localPlayerId).toBe('player-2');
  });

  // -------------------------------------------------------------------------
  // Full pawn-selection workflow (AC2 simulation at store level)
  // -------------------------------------------------------------------------

  it('full selection flow: setMoveOptions → clearSelection → setGamePhase(MOVING)', () => {
    // 1. Server sends move options
    useGameStore
      .getState()
      .setMoveOptions([
        { pawn_id: 1, target_pos: 5 },
        { pawn_id: 2, target_pos: 9 },
      ]);
    expect(useGameStore.getState().gamePhase).toBe('SELECTING');
    expect(useGameStore.getState().legalMoveIds).toContain(1);

    // 2. Player selects pawn 1 — client dispatches WS message (tested in
    //    Pawn3D.test.tsx) then clears highlights and advances the phase.
    useGameStore.getState().clearSelection();
    useGameStore.getState().setGamePhase('MOVING');

    const state = useGameStore.getState();
    expect(state.legalMoveIds).toHaveLength(0);
    expect(state.moveOptions).toHaveLength(0);
    expect(state.gamePhase).toBe('MOVING');
  });
});
