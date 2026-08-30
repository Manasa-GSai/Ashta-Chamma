import { describe, it, expect, beforeEach } from 'vitest';
import { useGameStore } from './gameStore';
import { GamePhase } from './types';

describe('useGameStore', () => {
  beforeEach(() => {
    useGameStore.setState({
      currentPlayerIndex: 0,
      currentRoll: null,
      gamePhase: GamePhase.WAITING,
      players: [],
      legalMoveIds: [],
      moveOptions: [],
      pawns: [],
      roomCode: null,
      roomStatus: 'WAITING',
      chatMessages: [],
      isChatOpen: false,
      connectionState: 'disconnected',
      reconnectAttempts: 0,
      connectionError: null,
      profile: null,
      isAuthenticated: false,
      errorMessage: null,
      isLoading: false,
    });
  });

  describe('initial state', () => {
    it('has currentPlayerIndex of 0', () => {
      const { currentPlayerIndex } = useGameStore.getState();
      expect(currentPlayerIndex).toBe(0);
    });

    it('has null currentRoll', () => {
      const { currentRoll } = useGameStore.getState();
      expect(currentRoll).toBeNull();
    });

    it('has WAITING gamePhase', () => {
      const { gamePhase } = useGameStore.getState();
      expect(gamePhase).toBe(GamePhase.WAITING);
    });

    it('has empty players array', () => {
      const { players } = useGameStore.getState();
      expect(players).toHaveLength(0);
    });

    it('has empty pawns array', () => {
      const { pawns } = useGameStore.getState();
      expect(pawns).toEqual([]);
    });
  });

  describe('setGamePhase', () => {
    it('transitions to ROLLING phase', () => {
      useGameStore.getState().setGamePhase(GamePhase.ROLLING);
      expect(useGameStore.getState().gamePhase).toBe(GamePhase.ROLLING);
    });

    it('transitions to SELECTING phase', () => {
      useGameStore.getState().setGamePhase(GamePhase.SELECTING);
      expect(useGameStore.getState().gamePhase).toBe(GamePhase.SELECTING);
    });

    it('transitions to MOVING phase', () => {
      useGameStore.getState().setGamePhase(GamePhase.MOVING);
      expect(useGameStore.getState().gamePhase).toBe(GamePhase.MOVING);
    });

    it('transitions to GAME_OVER phase', () => {
      useGameStore.getState().setGamePhase(GamePhase.GAME_OVER);
      expect(useGameStore.getState().gamePhase).toBe(GamePhase.GAME_OVER);
    });
  });

  describe('updateRoll', () => {
    it('updates currentRoll to the roll value', () => {
      useGameStore.getState().updateRoll({ value: 4, cowries: [true, false, true, false] });
      expect(useGameStore.getState().currentRoll).toBe(4);
    });

    it('updates to Ashta roll (all mouth-up)', () => {
      useGameStore.getState().updateRoll({ value: 8, cowries: [true, true, true, true] });
      expect(useGameStore.getState().currentRoll).toBe(8);
    });
  });

  describe('clearSelection', () => {
    it('resets legalMoveIds to empty array', () => {
      useGameStore.setState({ legalMoveIds: ['R1', 'G2'] });
      useGameStore.getState().clearSelection();
      expect(useGameStore.getState().legalMoveIds).toEqual([]);
    });
  });

  describe('setMoveOptions', () => {
    it('sets moveOptions and derives legalMoveIds from them', () => {
      useGameStore.getState().setMoveOptions([
        { pawn_id: 'R1', target_pos: 5 },
        { pawn_id: 'G2', target_pos: 12 },
      ]);
      const { moveOptions, legalMoveIds } = useGameStore.getState();
      expect(moveOptions).toHaveLength(2);
      expect(legalMoveIds).toEqual(['R1', 'G2']);
    });
  });

  describe('addChatMessage', () => {
    it('appends a message to chatMessages', () => {
      const msg = {
        id: '1',
        senderName: 'Alice',
        senderColor: 'red',
        text: 'Hello',
        timestamp: new Date().toISOString(),
      };
      useGameStore.getState().addChatMessage(msg);
      expect(useGameStore.getState().chatMessages).toHaveLength(1);
      expect(useGameStore.getState().chatMessages[0]).toEqual(msg);
    });
  });

  describe('toggleChat', () => {
    it('opens chat when closed', () => {
      useGameStore.setState({ isChatOpen: false });
      useGameStore.getState().toggleChat();
      expect(useGameStore.getState().isChatOpen).toBe(true);
    });

    it('closes chat when open', () => {
      useGameStore.setState({ isChatOpen: true });
      useGameStore.getState().toggleChat();
      expect(useGameStore.getState().isChatOpen).toBe(false);
    });
  });

  describe('connection state', () => {
    it('setConnectionState updates connectionState', () => {
      useGameStore.getState().setConnectionState('connecting');
      expect(useGameStore.getState().connectionState).toBe('connecting');
    });

    it('setConnectionError stores the error message', () => {
      useGameStore.getState().setConnectionError('Lost connection');
      expect(useGameStore.getState().connectionError).toBe('Lost connection');
    });

    it('setConnectionError clears the error when null', () => {
      useGameStore.getState().setConnectionError('err');
      useGameStore.getState().setConnectionError(null);
      expect(useGameStore.getState().connectionError).toBeNull();
    });
  });
});
