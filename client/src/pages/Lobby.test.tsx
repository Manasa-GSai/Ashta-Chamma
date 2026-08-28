import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Lobby, type LobbyPlayer } from './Lobby';

const PLAYERS: LobbyPlayer[] = [
  { id: 'p1', name: 'Alice', color: '#000', isReady: true, isHost: true },
  { id: 'p2', name: 'Bob', color: '#333', isReady: false, isHost: false },
];

function buildProps(overrides: Partial<Parameters<typeof Lobby>[0]> = {}) {
  return {
    players: [],
    isHost: false,
    isReady: false,
    canStart: false,
    onCreateRoom: vi.fn(),
    onJoinRoom: vi.fn(),
    onToggleReady: vi.fn(),
    onStartGame: vi.fn(),
    onLeave: vi.fn(),
    ...overrides,
  };
}

describe('Lobby — pre-room (no roomCode)', () => {
  it('renders a "Create Room" button', () => {
    render(<Lobby {...buildProps()} />);
    expect(
      screen.getByRole('button', { name: /create a new game room/i }),
    ).toBeInTheDocument();
  });

  it('calls onCreateRoom when "Create Room" button is clicked', () => {
    const onCreateRoom = vi.fn();
    render(<Lobby {...buildProps({ onCreateRoom })} />);
    fireEvent.click(
      screen.getByRole('button', { name: /create a new game room/i }),
    );
    expect(onCreateRoom).toHaveBeenCalledTimes(1);
  });

  it('renders a labelled room code input', () => {
    render(<Lobby {...buildProps()} />);
    // Label association: getByLabelText looks for htmlFor/id pairing.
    expect(screen.getByLabelText(/room code/i)).toBeInTheDocument();
  });

  it('renders a "Join Room" submit button that is initially disabled', () => {
    render(<Lobby {...buildProps()} />);
    const joinBtn = screen.getByRole('button', {
      name: /join the room with the entered code/i,
    });
    expect(joinBtn).toBeDisabled();
  });

  it('enables "Join Room" button when room code is entered', () => {
    render(<Lobby {...buildProps()} />);
    const input = screen.getByLabelText(/enter 6-character room code/i);
    fireEvent.change(input, { target: { value: 'ABC123' } });
    const joinBtn = screen.getByRole('button', {
      name: /join the room with the entered code/i,
    });
    expect(joinBtn).not.toBeDisabled();
  });

  it('calls onJoinRoom with uppercased code on form submit', () => {
    const onJoinRoom = vi.fn();
    render(<Lobby {...buildProps({ onJoinRoom })} />);
    const input = screen.getByLabelText(/enter 6-character room code/i);
    fireEvent.change(input, { target: { value: 'abc123' } });
    fireEvent.submit(screen.getByRole('form', { name: /join an existing room/i }));
    expect(onJoinRoom).toHaveBeenCalledWith('ABC123');
  });

  it('calls onJoinRoom with uppercased code when Enter is pressed in input', () => {
    const onJoinRoom = vi.fn();
    render(<Lobby {...buildProps({ onJoinRoom })} />);
    const input = screen.getByLabelText(/enter 6-character room code/i);
    fireEvent.change(input, { target: { value: 'XYZ789' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onJoinRoom).toHaveBeenCalledWith('XYZ789');
  });
});

describe('Lobby — in-room (with roomCode)', () => {
  const inRoomProps = buildProps({
    roomCode: 'ABC123',
    players: PLAYERS,
  });

  it('displays the room code', () => {
    render(<Lobby {...inRoomProps} />);
    expect(screen.getByText('ABC123')).toBeInTheDocument();
  });

  it('renders the player list', () => {
    render(<Lobby {...inRoomProps} />);
    expect(screen.getByText(/Alice/)).toBeInTheDocument();
    expect(screen.getByText(/Bob/)).toBeInTheDocument();
  });

  it('renders a "Ready" toggle button with aria-pressed="false" when not ready', () => {
    render(<Lobby {...inRoomProps} />);
    const readyBtn = screen.getByRole('button', { name: /mark yourself as ready/i });
    expect(readyBtn).toHaveAttribute('aria-pressed', 'false');
  });

  it('renders toggle button with aria-pressed="true" when ready', () => {
    render(<Lobby {...buildProps({ roomCode: 'ABC123', players: [], isReady: true })} />);
    const btn = screen.getByRole('button', { name: /mark yourself as not ready/i });
    expect(btn).toHaveAttribute('aria-pressed', 'true');
  });

  it('calls onToggleReady when the ready button is clicked', () => {
    const onToggleReady = vi.fn();
    render(<Lobby {...buildProps({ roomCode: 'ABC123', players: [], onToggleReady })} />);
    fireEvent.click(screen.getByRole('button', { name: /mark yourself as ready/i }));
    expect(onToggleReady).toHaveBeenCalledTimes(1);
  });

  it('does not render "Start Game" button for non-hosts', () => {
    render(<Lobby {...buildProps({ roomCode: 'ABC123', players: [], isHost: false })} />);
    expect(
      screen.queryByRole('button', { name: /start the game/i }),
    ).not.toBeInTheDocument();
  });

  it('renders a disabled "Start Game" button for host when canStart is false', () => {
    render(
      <Lobby
        {...buildProps({
          roomCode: 'ABC123',
          players: [],
          isHost: true,
          canStart: false,
        })}
      />,
    );
    expect(
      screen.getByRole('button', { name: /start the game/i }),
    ).toBeDisabled();
  });

  it('renders an enabled "Start Game" button when host and canStart is true', () => {
    render(
      <Lobby
        {...buildProps({
          roomCode: 'ABC123',
          players: [],
          isHost: true,
          canStart: true,
        })}
      />,
    );
    expect(
      screen.getByRole('button', { name: /start the game/i }),
    ).not.toBeDisabled();
  });

  it('calls onStartGame when Start Game is clicked', () => {
    const onStartGame = vi.fn();
    render(
      <Lobby
        {...buildProps({
          roomCode: 'ABC123',
          players: [],
          isHost: true,
          canStart: true,
          onStartGame,
        })}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /start the game/i }));
    expect(onStartGame).toHaveBeenCalledTimes(1);
  });

  it('renders a "Leave" button and calls onLeave when clicked', () => {
    const onLeave = vi.fn();
    render(
      <Lobby
        {...buildProps({ roomCode: 'ABC123', players: [], onLeave })}
      />,
    );
    fireEvent.click(
      screen.getByRole('button', { name: /leave the lobby/i }),
    );
    expect(onLeave).toHaveBeenCalledTimes(1);
  });
});
