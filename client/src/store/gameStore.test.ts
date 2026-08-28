import { describe, it, expect, beforeEach } from 'vitest';
import { useGameStore } from './gameStore';

describe('useGameStore', () => {
  beforeEach(() => {
    // Reset to initial state before each test
    useGameStore.setState({
      currentPlayer: 0,
      rollResult: null,
      phase: 'WAITING',
      players: [],
      boardState: {},
    });
  });

  describe('initial state', () => {
    it('has currentPlayer of 0', () => {
      const { currentPlayer } = useGameStore.getState();
      expect(currentPlayer).toBe(0);
    });

    it('has null rollResult', () => {
      const { rollResult } = useGameStore.getState();
      expect(rollResult).toBeNull();
    });

    it('has WAITING phase', () => {
      const { phase } = useGameStore.getState();
      expect(phase).toBe('WAITING');
    });

    it('has empty players array', () => {
      const { players } = useGameStore.getState();
      expect(players).toHaveLength(0);
    });

    it('has empty boardState', () => {
      const { boardState } = useGameStore.getState();
      expect(boardState).toEqual({});
    });
  });

  describe('setCurrentPlayer', () => {
    it('updates currentPlayer to given value', () => {
      useGameStore.getState().setCurrentPlayer(2);
      expect(useGameStore.getState().currentPlayer).toBe(2);
    });

    it('updates currentPlayer to player index 3', () => {
      useGameStore.getState().setCurrentPlayer(3);
      expect(useGameStore.getState().currentPlayer).toBe(3);
    });

    it('does not affect other state fields', () => {
      useGameStore.getState().setCurrentPlayer(1);
      const { rollResult, phase } = useGameStore.getState();
      expect(rollResult).toBeNull();
      expect(phase).toBe('WAITING');
    });
  });

  describe('setRollResult', () => {
    it('updates rollResult to a number', () => {
      useGameStore.getState().setRollResult(4);
      expect(useGameStore.getState().rollResult).toBe(4);
    });

    it('updates rollResult to 8 (Ashta)', () => {
      useGameStore.getState().setRollResult(8);
      expect(useGameStore.getState().rollResult).toBe(8);
    });

    it('can set rollResult back to null', () => {
      useGameStore.getState().setRollResult(4);
      useGameStore.getState().setRollResult(null);
      expect(useGameStore.getState().rollResult).toBeNull();
    });
  });

  describe('setPhase', () => {
    it('transitions to ROLLING phase', () => {
      useGameStore.getState().setPhase('ROLLING');
      expect(useGameStore.getState().phase).toBe('ROLLING');
    });

    it('transitions to SELECTING phase', () => {
      useGameStore.getState().setPhase('SELECTING');
      expect(useGameStore.getState().phase).toBe('SELECTING');
    });

    it('transitions to MOVING phase', () => {
      useGameStore.getState().setPhase('MOVING');
      expect(useGameStore.getState().phase).toBe('MOVING');
    });

    it('transitions to GAME_OVER phase', () => {
      useGameStore.getState().setPhase('GAME_OVER');
      expect(useGameStore.getState().phase).toBe('GAME_OVER');
    });
  });

  describe('resetGame', () => {
    it('resets currentPlayer to 0', () => {
      useGameStore.getState().setCurrentPlayer(3);
      useGameStore.getState().resetGame();
      expect(useGameStore.getState().currentPlayer).toBe(0);
    });

    it('resets rollResult to null', () => {
      useGameStore.getState().setRollResult(8);
      useGameStore.getState().resetGame();
      expect(useGameStore.getState().rollResult).toBeNull();
    });

    it('resets phase to WAITING', () => {
      useGameStore.getState().setPhase('GAME_OVER');
      useGameStore.getState().resetGame();
      expect(useGameStore.getState().phase).toBe('WAITING');
    });

    it('resets entire state when multiple fields are modified', () => {
      useGameStore.setState({
        currentPlayer: 2,
        rollResult: 4,
        phase: 'MOVING',
        players: ['Alice', 'Bob'],
      });
      useGameStore.getState().resetGame();
      const state = useGameStore.getState();
      expect(state.currentPlayer).toBe(0);
      expect(state.rollResult).toBeNull();
      expect(state.phase).toBe('WAITING');
    });
  });
});
