import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { GameHUD } from './GameHUD';
import { useGameStore } from '../../store/gameStore';
import type { RoomPlayer } from '../../store/types';
import { GamePhase } from '../../store/types';

const makePlayer = (name: string, index: number): RoomPlayer => ({
  id: `player-${index}`,
  name,
  color: (['RED', 'GREEN', 'YELLOW', 'BLUE'] as const)[index % 4],
  isAI: false,
  isConnected: true,
});

describe('GameHUD', () => {
  beforeEach(() => {
    useGameStore.setState({
      currentPlayerIndex: 0,
      currentRoll: null,
      gamePhase: GamePhase.ROLLING,
      players: ['Alice', 'Bob', 'Charlie', 'Diana'].map(makePlayer),
    });
  });

  describe('current player display', () => {
    it('displays the current player name from the store', () => {
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Alice');
    });

    it('displays the second player when currentPlayerIndex is 1', () => {
      useGameStore.setState({ currentPlayerIndex: 1 });
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Bob');
    });

    it('falls back to "Player N" label when players array has no name at index', () => {
      useGameStore.setState({ currentPlayerIndex: 0, players: [] });
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Player 1');
    });

    it('updates displayed player when store changes', () => {
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Alice');

      act(() => {
        useGameStore.setState({ currentPlayerIndex: 2 });
      });

      expect(screen.getByTestId('current-player')).toHaveTextContent('Charlie');
    });
  });

  describe('roll result display', () => {
    it('does not show roll result when currentRoll is null', () => {
      render(<GameHUD />);
      expect(screen.queryByTestId('roll-result')).not.toBeInTheDocument();
    });

    it('shows roll result when a value is set in the store', () => {
      useGameStore.setState({ currentRoll: 4 });
      render(<GameHUD />);
      expect(screen.getByTestId('roll-result')).toHaveTextContent('4');
    });

    it('shows Ashta roll result of 8', () => {
      useGameStore.setState({ currentRoll: 8 });
      render(<GameHUD />);
      expect(screen.getByTestId('roll-result')).toHaveTextContent('8');
    });

    it('updates roll result display when store changes', () => {
      render(<GameHUD />);
      expect(screen.queryByTestId('roll-result')).not.toBeInTheDocument();

      act(() => {
        useGameStore.getState().updateRoll({ value: 3, cowries: [true, false, true, false] });
      });

      expect(screen.getByTestId('roll-result')).toHaveTextContent('3');
    });

    it('hides roll result after it is reset', () => {
      useGameStore.setState({ currentRoll: 2 });
      render(<GameHUD />);
      expect(screen.getByTestId('roll-result')).toBeInTheDocument();

      act(() => {
        useGameStore.setState({ currentRoll: null });
      });

      expect(screen.queryByTestId('roll-result')).not.toBeInTheDocument();
    });
  });
});
