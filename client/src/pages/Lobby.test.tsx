import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { Lobby } from './Lobby';

describe('Lobby', () => {
  describe('rendering', () => {
    it('renders the room code input', () => {
      render(<Lobby />);
      expect(screen.getByLabelText(/room code/i)).toBeInTheDocument();
    });

    it('renders the Join Room button', () => {
      render(<Lobby />);
      expect(screen.getByRole('button', { name: /join room/i })).toBeInTheDocument();
    });

    it('renders no error message initially', () => {
      render(<Lobby />);
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  describe('room code validation', () => {
    it('shows an error when room code is too short', async () => {
      render(<Lobby />);
      await userEvent.type(screen.getByLabelText(/room code/i), 'AB');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('shows an error when room code is empty', async () => {
      render(<Lobby />);
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('shows an error when room code contains special characters', async () => {
      render(<Lobby />);
      await userEvent.type(screen.getByLabelText(/room code/i), 'AB!@12');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    it('shows an error when room code is too long after trimming', async () => {
      render(<Lobby />);
      // maxLength=6 prevents more than 6 chars, but test with exactly 5 chars
      await userEvent.type(screen.getByLabelText(/room code/i), 'ABCDE');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  describe('valid room code submission', () => {
    it('calls onJoin with the entered code when code is valid', async () => {
      const onJoin = vi.fn();
      render(<Lobby onJoin={onJoin} />);
      await userEvent.type(screen.getByLabelText(/room code/i), 'ABC123');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(onJoin).toHaveBeenCalledWith('ABC123');
    });

    it('calls onJoin with all-digit code', async () => {
      const onJoin = vi.fn();
      render(<Lobby onJoin={onJoin} />);
      await userEvent.type(screen.getByLabelText(/room code/i), '123456');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(onJoin).toHaveBeenCalledWith('123456');
    });

    it('normalises lowercase input to uppercase before calling onJoin', async () => {
      const onJoin = vi.fn();
      render(<Lobby onJoin={onJoin} />);
      // The component converts input to uppercase on change
      await userEvent.type(screen.getByLabelText(/room code/i), 'abcdef');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(onJoin).toHaveBeenCalledWith('ABCDEF');
    });

    it('does not show an error when code is valid', async () => {
      render(<Lobby />);
      await userEvent.type(screen.getByLabelText(/room code/i), 'XYZ789');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('calls onJoin only once per submit', async () => {
      const onJoin = vi.fn();
      render(<Lobby onJoin={onJoin} />);
      await userEvent.type(screen.getByLabelText(/room code/i), 'ABC123');
      await userEvent.click(screen.getByRole('button', { name: /join room/i }));
      expect(onJoin).toHaveBeenCalledTimes(1);
    });
  });
});
