import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { GameHUD, type GameHUDProps, type PlayerInfo, type PawnInfo } from './GameHUD';

/** Minimal valid props for the GameHUD. */
const PLAYER: PlayerInfo = { id: 'p1', name: 'Alice', color: '#000000', score: 0 };
const PLAYER2: PlayerInfo = { id: 'p2', name: 'Bob', color: '#333333', score: 2 };
const PAWN: PawnInfo = { id: 1, color: 'red', position: 5 };

function buildProps(overrides: Partial<GameHUDProps> = {}): GameHUDProps {
  return {
    currentPlayer: PLAYER,
    isCurrentUserTurn: false,
    phase: 'rolling',
    legalPawns: [],
    players: [PLAYER, PLAYER2],
    onRoll: vi.fn(),
    onSelectPawn: vi.fn(),
    ...overrides,
  };
}

describe('GameHUD', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('ARIA structure', () => {
    it('renders a region landmark with label "Game HUD"', () => {
      render(<GameHUD {...buildProps()} />);
      expect(
        screen.getByRole('region', { name: /game hud/i }),
      ).toBeInTheDocument();
    });

    it('renders a status element for the turn indicator', () => {
      render(<GameHUD {...buildProps()} />);
      // Multiple status roles may exist (turn + announcer); at least one present.
      const statuses = screen.getAllByRole('status');
      expect(statuses.length).toBeGreaterThanOrEqual(1);
    });

    it('renders a list of player scores', () => {
      render(<GameHUD {...buildProps()} />);
      expect(screen.getByRole('list')).toBeInTheDocument();
    });

    it('displays both player names in the score list', () => {
      render(<GameHUD {...buildProps()} />);
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
      expect(screen.getByText(/Bob/)).toBeInTheDocument();
    });
  });

  describe('Roll button', () => {
    it('shows Roll button only when it is the user\'s turn in rolling phase', () => {
      render(
        <GameHUD
          {...buildProps({ isCurrentUserTurn: true, phase: 'rolling' })}
        />,
      );
      expect(
        screen.getByRole('button', { name: /roll cowrie shells/i }),
      ).toBeInTheDocument();
    });

    it('hides Roll button when it is NOT the user\'s turn', () => {
      render(
        <GameHUD
          {...buildProps({ isCurrentUserTurn: false, phase: 'rolling' })}
        />,
      );
      expect(
        screen.queryByRole('button', { name: /roll cowrie shells/i }),
      ).not.toBeInTheDocument();
    });

    it('calls onRoll when the Roll button is clicked', () => {
      const onRoll = vi.fn();
      render(
        <GameHUD
          {...buildProps({ isCurrentUserTurn: true, phase: 'rolling', onRoll })}
        />,
      );
      fireEvent.click(screen.getByRole('button', { name: /roll cowrie shells/i }));
      expect(onRoll).toHaveBeenCalledTimes(1);
    });

    it('calls onRoll when Space is pressed on the Roll button', () => {
      const onRoll = vi.fn();
      render(
        <GameHUD
          {...buildProps({ isCurrentUserTurn: true, phase: 'rolling', onRoll })}
        />,
      );
      fireEvent.keyDown(
        screen.getByRole('button', { name: /roll cowrie shells/i }),
        { key: ' ' },
      );
      expect(onRoll).toHaveBeenCalledTimes(1);
    });
  });

  describe('Pawn selection', () => {
    it('renders pawn buttons during selecting phase with legal pawns', () => {
      render(
        <GameHUD
          {...buildProps({
            isCurrentUserTurn: true,
            phase: 'selecting',
            legalPawns: [PAWN],
          })}
        />,
      );
      expect(
        screen.getByRole('button', { name: /move red pawn at position 5/i }),
      ).toBeInTheDocument();
    });

    it('calls onSelectPawn with the correct pawn id when a pawn button is clicked', () => {
      const onSelectPawn = vi.fn();
      render(
        <GameHUD
          {...buildProps({
            isCurrentUserTurn: true,
            phase: 'selecting',
            legalPawns: [PAWN],
            onSelectPawn,
          })}
        />,
      );
      fireEvent.click(
        screen.getByRole('button', { name: /move red pawn at position 5/i }),
      );
      expect(onSelectPawn).toHaveBeenCalledWith(PAWN.id);
    });

    it('renders a group landmark for pawn selection', () => {
      render(
        <GameHUD
          {...buildProps({
            isCurrentUserTurn: true,
            phase: 'selecting',
            legalPawns: [PAWN],
          })}
        />,
      );
      expect(screen.getByRole('group')).toBeInTheDocument();
    });
  });

  describe('Game over state', () => {
    it('renders an alert role on game over', () => {
      render(
        <GameHUD
          {...buildProps({ phase: 'game_over', winnerName: 'Alice' })}
        />,
      );
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('displays the winner name in the result', () => {
      render(
        <GameHUD
          {...buildProps({ phase: 'game_over', winnerName: 'Alice' })}
        />,
      );
      expect(screen.getByText(/Alice wins!/i)).toBeInTheDocument();
    });
  });

  describe('Screen reader announcements', () => {
    it('announces "Your turn to roll" when it is the user\'s turn in rolling phase', async () => {
      render(
        <GameHUD
          {...buildProps({ isCurrentUserTurn: true, phase: 'rolling' })}
        />,
      );
      await act(async () => {
        vi.advanceTimersByTime(50);
      });
      const announcer = document.querySelector('[aria-live="polite"]');
      expect(announcer?.textContent).toMatch(/your turn to roll/i);
    });

    it('announces roll value when rollValue prop changes', async () => {
      const { rerender } = render(<GameHUD {...buildProps()} />);

      rerender(<GameHUD {...buildProps({ rollValue: 4 })} />);
      await act(async () => {
        vi.advanceTimersByTime(50);
      });

      const announcer = document.querySelector('[aria-live="polite"]');
      expect(announcer?.textContent).toMatch(/rolled 4/i);
    });

    it('announces lastMoveDescription when provided', async () => {
      render(
        <GameHUD
          {...buildProps({
            lastMoveDescription: 'Red pawn moved to position 8',
          })}
        />,
      );
      await act(async () => {
        vi.advanceTimersByTime(50);
      });
      const announcer = document.querySelector('[aria-live="polite"]');
      expect(announcer?.textContent).toMatch(/red pawn moved to position 8/i);
    });

    it('announces captureDescription when provided', async () => {
      render(
        <GameHUD
          {...buildProps({ captureDescription: 'Red captured Blue pawn' })}
        />,
      );
      await act(async () => {
        vi.advanceTimersByTime(50);
      });
      const announcer = document.querySelector('[aria-live="polite"]');
      expect(announcer?.textContent).toMatch(/red captured blue pawn/i);
    });

    it('announces winner on game over', async () => {
      render(
        <GameHUD
          {...buildProps({ phase: 'game_over', winnerName: 'Alice' })}
        />,
      );
      await act(async () => {
        vi.advanceTimersByTime(50);
      });
      const announcer = document.querySelector('[aria-live="polite"]');
      expect(announcer?.textContent).toMatch(/alice player wins!/i);
    });
  });
});
