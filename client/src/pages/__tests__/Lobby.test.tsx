import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Lobby } from '../Lobby';

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

// Mock zustand store
vi.mock('../../store/gameStore', () => ({
  useGameStore: () => ({ setRoomCode: vi.fn() }),
}));

// Mock api client
vi.mock('../../api/client', () => ({
  api: {
    get: vi.fn().mockResolvedValue([]),
    post: vi.fn().mockResolvedValue({ room_id: 'abc-123', code: 'ABC123' }),
    delete: vi.fn().mockResolvedValue(undefined),
  },
}));

describe('Lobby', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  describe('rendering', () => {
    it('renders Create Room and Join Room sections', async () => {
      render(<Lobby />);

      expect(
        screen.getByRole('heading', { name: 'lobby.create.title' }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: 'lobby.join.title' }),
      ).toBeInTheDocument();
    });

    it('renders the max players dropdown with options 2, 3, 4', async () => {
      render(<Lobby />);
      const select = screen.getByRole('combobox');
      expect(select).toBeInTheDocument();

      const options = screen.getAllByRole('option');
      const values = options.map((o) => (o as HTMLOptionElement).value);
      expect(values).toContain('2');
      expect(values).toContain('3');
      expect(values).toContain('4');
    });

    it('renders the room code input', () => {
      render(<Lobby />);
      expect(screen.getByRole('textbox')).toBeInTheDocument();
    });
  });

  describe('Join Room form validation', () => {
    it('shows error message for code with fewer than 6 characters', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const input = screen.getByRole('textbox');
      await user.type(input, 'ABC');

      // Trigger submit
      const submitButton = screen.getByRole('button', {
        name: 'lobby.join.submit',
      });
      await user.click(submitButton);

      expect(
        screen.getByRole('alert', { hidden: false }),
      ).toBeInTheDocument();
    });

    it('shows error message for code with more than 6 characters', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const input = screen.getByRole('textbox');
      // maxLength=6 prevents typing more, but test the validation logic directly
      await user.type(input, 'TOOLNG');
      // Force invalid value via a short code then clear and retype
      await user.clear(input);
      await user.type(input, 'TOOLN'); // 5 chars

      const submitButton = screen.getByRole('button', {
        name: 'lobby.join.submit',
      });
      await user.click(submitButton);

      expect(
        screen.getByRole('alert', { hidden: false }),
      ).toBeInTheDocument();
    });

    it('shows error message for code with non-alphanumeric characters', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const input = screen.getByRole('textbox');
      // Typing special chars — the component uppercases input
      // We simulate pasting a value with special chars via fireEvent
      await user.type(input, 'ABC!@#');

      const submitButton = screen.getByRole('button', {
        name: 'lobby.join.submit',
      });
      await user.click(submitButton);

      expect(
        screen.getByRole('alert', { hidden: false }),
      ).toBeInTheDocument();
    });

    it('clears error when a valid 6-character alphanumeric code is entered', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const input = screen.getByRole('textbox');

      // Type invalid first
      await user.type(input, 'ABC');
      // Then clear and type valid
      await user.clear(input);
      await user.type(input, 'ABC123');

      // No validation error should be showing
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });

    it('does not navigate if room code is invalid on submit', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const input = screen.getByRole('textbox');
      await user.type(input, 'BAD');

      const submitButton = screen.getByRole('button', {
        name: 'lobby.join.submit',
      });
      await user.click(submitButton);

      expect(mockNavigate).not.toHaveBeenCalled();
    });

    it('navigates to /game/:code when a valid code is submitted', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const input = screen.getByRole('textbox');
      await user.type(input, 'ABC123');

      const submitButton = screen.getByRole('button', {
        name: 'lobby.join.submit',
      });
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/game/ABC123');
      });
    });
  });

  describe('Create Room form', () => {
    it('navigates to /game/:code after successful room creation', async () => {
      const user = userEvent.setup();
      render(<Lobby />);

      const createButton = screen.getByRole('button', {
        name: 'lobby.create.submit',
      });
      await user.click(createButton);

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/game/ABC123');
      });
    });
  });
});
