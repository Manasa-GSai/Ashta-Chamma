import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, beforeEach } from 'vitest';
import { GameHUD } from './GameHUD';
import { useGameStore } from '../../store/gameStore';

describe('GameHUD', () => {
  beforeEach(() => {
    // Reset store to a known state before each test
    useGameStore.setState({
      currentPlayer: 0,
      rollResult: null,
      players: ['Alice', 'Bob', 'Charlie', 'Diana'],
      phase: 'ROLLING',
      boardState: {},
    });
  });

  describe('current player display', () => {
    it('displays the current player name from the store', () => {
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Alice');
    });

    it('displays the second player when currentPlayer is 1', () => {
      useGameStore.setState({ currentPlayer: 1 });
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Bob');
    });

    it('falls back to "Player N" label when players array has no name at index', () => {
      useGameStore.setState({ currentPlayer: 0, players: [] });
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Player 1');
    });

    it('updates displayed player when store changes', () => {
      render(<GameHUD />);
      expect(screen.getByTestId('current-player')).toHaveTextContent('Alice');

      act(() => {
        useGameStore.getState().setCurrentPlayer(2);
      });

      expect(screen.getByTestId('current-player')).toHaveTextContent('Charlie');
    });
  });

  describe('roll result display', () => {
    it('does not show roll result when rollResult is null', () => {
      render(<GameHUD />);
      expect(screen.queryByTestId('roll-result')).not.toBeInTheDocument();
    });

    it('shows roll result when a value is set in the store', () => {
      useGameStore.setState({ rollResult: 4 });
      render(<GameHUD />);
      expect(screen.getByTestId('roll-result')).toHaveTextContent('4');
    });

    it('shows Ashta roll result of 8', () => {
      useGameStore.setState({ rollResult: 8 });
      render(<GameHUD />);
      expect(screen.getByTestId('roll-result')).toHaveTextContent('8');
    });

    it('updates roll result display when store changes', () => {
      render(<GameHUD />);
      expect(screen.queryByTestId('roll-result')).not.toBeInTheDocument();

      act(() => {
        useGameStore.getState().setRollResult(3);
      });

      expect(screen.getByTestId('roll-result')).toHaveTextContent('3');
    });

    it('hides roll result after it is reset to null', () => {
      useGameStore.setState({ rollResult: 2 });
      render(<GameHUD />);
      expect(screen.getByTestId('roll-result')).toBeInTheDocument();

      act(() => {
        useGameStore.getState().setRollResult(null);
      });

      expect(screen.queryByTestId('roll-result')).not.toBeInTheDocument();
    });
  });
});
