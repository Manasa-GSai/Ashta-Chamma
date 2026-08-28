import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { MainMenu } from './MainMenu';

describe('MainMenu', () => {
  describe('rendering', () => {
    it('renders a Play button', () => {
      render(<MainMenu />);
      expect(screen.getByRole('button', { name: /play/i })).toBeInTheDocument();
    });

    it('renders a Rules button', () => {
      render(<MainMenu />);
      expect(screen.getByRole('button', { name: /rules/i })).toBeInTheDocument();
    });

    it('renders the game title heading', () => {
      render(<MainMenu />);
      expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
    });
  });

  describe('interactions', () => {
    it('calls onPlay when the Play button is clicked', async () => {
      const onPlay = vi.fn();
      render(<MainMenu onPlay={onPlay} />);
      await userEvent.click(screen.getByRole('button', { name: /play/i }));
      expect(onPlay).toHaveBeenCalledOnce();
    });

    it('calls onRules when the Rules button is clicked', async () => {
      const onRules = vi.fn();
      render(<MainMenu onRules={onRules} />);
      await userEvent.click(screen.getByRole('button', { name: /rules/i }));
      expect(onRules).toHaveBeenCalledOnce();
    });

    it('does not throw when Play is clicked without onPlay handler', async () => {
      render(<MainMenu />);
      await expect(
        userEvent.click(screen.getByRole('button', { name: /play/i })),
      ).resolves.not.toThrow();
    });

    it('does not throw when Rules is clicked without onRules handler', async () => {
      render(<MainMenu />);
      await expect(
        userEvent.click(screen.getByRole('button', { name: /rules/i })),
      ).resolves.not.toThrow();
    });
  });
});
