import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MainMenu } from './MainMenu';

describe('MainMenu', () => {
  describe('ARIA and keyboard structure', () => {
    it('renders a main landmark', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('renders a navigation landmark', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(screen.getByRole('navigation')).toBeInTheDocument();
    });

    it('contains a skip-to-content link', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(screen.getByText(/skip to main content/i)).toBeInTheDocument();
    });

    it('renders the page heading', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(
        screen.getByRole('heading', { name: /ashta chamma 3d/i }),
      ).toBeInTheDocument();
    });
  });

  describe('Buttons', () => {
    it('renders a "New Game" button with descriptive aria-label', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(
        screen.getByRole('button', { name: /start a new game/i }),
      ).toBeInTheDocument();
    });

    it('renders a "Join Game" button with descriptive aria-label', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(
        screen.getByRole('button', { name: /join an existing game/i }),
      ).toBeInTheDocument();
    });

    it('renders a "Settings" button with descriptive aria-label', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      expect(
        screen.getByRole('button', { name: /open settings/i }),
      ).toBeInTheDocument();
    });

    it('all three buttons have type="button" to prevent accidental form submission', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      const buttons = screen.getAllByRole('button');
      buttons.forEach((btn) => {
        expect(btn).toHaveAttribute('type', 'button');
      });
    });
  });

  describe('Callback wiring', () => {
    it('calls onNewGame when "New Game" button is clicked', () => {
      const onNewGame = vi.fn();
      render(
        <MainMenu onNewGame={onNewGame} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      fireEvent.click(screen.getByRole('button', { name: /start a new game/i }));
      expect(onNewGame).toHaveBeenCalledTimes(1);
    });

    it('calls onJoinGame when "Join Game" button is clicked', () => {
      const onJoinGame = vi.fn();
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={onJoinGame} onSettings={vi.fn()} />,
      );
      fireEvent.click(screen.getByRole('button', { name: /join an existing game/i }));
      expect(onJoinGame).toHaveBeenCalledTimes(1);
    });

    it('calls onSettings when "Settings" button is clicked', () => {
      const onSettings = vi.fn();
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={onSettings} />,
      );
      fireEvent.click(screen.getByRole('button', { name: /open settings/i }));
      expect(onSettings).toHaveBeenCalledTimes(1);
    });
  });

  describe('Skip link', () => {
    it('skip link becomes visible on focus', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      const skipLink = screen.getByText(/skip to main content/i);
      // Before focus the link should be off-screen.
      expect(skipLink).toHaveStyle({ left: '-9999px' });

      fireEvent.focus(skipLink);
      // After focus the link should be visible.
      expect(skipLink).toHaveStyle({ left: '0' });
    });

    it('skip link moves focus to main content on click', () => {
      render(
        <MainMenu onNewGame={vi.fn()} onJoinGame={vi.fn()} onSettings={vi.fn()} />,
      );
      const skipLink = screen.getByText(/skip to main content/i);
      const main = screen.getByRole('main');
      fireEvent.click(skipLink);
      // Focus should have moved to the main element.
      expect(document.activeElement).toBe(main);
    });
  });
});
