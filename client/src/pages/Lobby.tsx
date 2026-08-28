import { useState, useRef } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';

export interface LobbyPlayer {
  id: string;
  name: string;
  color: string;
  isReady: boolean;
  isHost: boolean;
}

export interface LobbyProps {
  /** Active room code; undefined if no room has been joined/created yet. */
  roomCode?: string;
  players: LobbyPlayer[];
  isHost: boolean;
  isReady: boolean;
  /** Whether all players are ready and game can start (host only). */
  canStart: boolean;
  onCreateRoom: () => void;
  onJoinRoom: (code: string) => void;
  onToggleReady: () => void;
  onStartGame: () => void;
  onLeave: () => void;
}

/**
 * Lobby page with keyboard-accessible form inputs, explicit label associations,
 * and ARIA roles/labels on all custom interactive elements.
 *
 * Form inputs follow WCAG 1.3.1 (Info and Relationships) by associating every
 * input with a <label> via htmlFor/id.  The Submit button is disabled (with
 * aria-disabled) when no room code has been entered, giving screen reader users
 * advance notice that the action is unavailable.
 */
export const Lobby = ({
  roomCode,
  players,
  isHost,
  isReady,
  canStart,
  onCreateRoom,
  onJoinRoom,
  onToggleReady,
  onStartGame,
  onLeave,
}: LobbyProps): JSX.Element => {
  const [joinCodeInput, setJoinCodeInput] = useState<string>('');
  const joinInputRef = useRef<HTMLInputElement>(null);

  const handleJoinSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = joinCodeInput.trim().toUpperCase();
    if (trimmed) {
      onJoinRoom(trimmed);
    }
  };

  const handleJoinInputKeyDown = (
    event: KeyboardEvent<HTMLInputElement>,
  ) => {
    // Enter submits the form — handled by native form submit; Space is a
    // normal character in a text field so we do not override it here.
    if (event.key === 'Enter') {
      const trimmed = joinCodeInput.trim().toUpperCase();
      if (trimmed) {
        onJoinRoom(trimmed);
      }
    }
  };

  return (
    <main aria-label="Game lobby">
      <h1>Game Lobby</h1>

      {roomCode === undefined ? (
        /* Pre-room section: create or join */
        <section aria-label="Room options">
          <button
            type="button"
            onClick={onCreateRoom}
            aria-label="Create a new game room"
          >
            Create Room
          </button>

          <form
            onSubmit={handleJoinSubmit}
            aria-label="Join an existing room by code"
          >
            <div>
              {/* Explicit label association via htmlFor/id (WCAG 1.3.1) */}
              <label htmlFor="room-code-input">Room Code</label>
              <input
                id="room-code-input"
                ref={joinInputRef}
                type="text"
                value={joinCodeInput}
                onChange={(e) =>
                  setJoinCodeInput(e.target.value.toUpperCase())
                }
                onKeyDown={handleJoinInputKeyDown}
                placeholder="e.g. ABC123"
                aria-label="Enter 6-character room code"
                aria-required="true"
                maxLength={6}
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <button
              type="submit"
              aria-label="Join the room with the entered code"
              aria-disabled={!joinCodeInput.trim()}
              disabled={!joinCodeInput.trim()}
            >
              Join Room
            </button>
          </form>
        </section>
      ) : (
        /* In-room section: player list and lobby controls */
        <section aria-label="Room information">
          <p>
            Room Code:{' '}
            <strong aria-label={`Room code: ${roomCode}`}>{roomCode}</strong>
          </p>

          <section aria-label="Players in lobby">
            <h2>Players</h2>
            <ul>
              {players.map((player) => (
                <li key={player.id}>
                  {/*
                   * Color alone must not convey meaning (WCAG 1.4.1).
                   * Host/ready status is conveyed in text AND aria-label.
                   */}
                  <span
                    aria-label={[
                      player.name,
                      player.isHost ? 'host' : null,
                      player.isReady ? 'ready' : 'not ready',
                    ]
                      .filter(Boolean)
                      .join(', ')}
                  >
                    {player.name}
                    {player.isHost && ' (Host)'}
                    {player.isReady ? ' ✓' : ' …'}
                  </span>
                </li>
              ))}
            </ul>
          </section>

          <div role="group" aria-label="Lobby actions">
            {/* Toggle button — aria-pressed communicates current state */}
            <button
              type="button"
              onClick={onToggleReady}
              aria-label={
                isReady
                  ? 'Mark yourself as not ready'
                  : 'Mark yourself as ready'
              }
              aria-pressed={isReady}
            >
              {isReady ? 'Not Ready' : 'Ready'}
            </button>

            {isHost && (
              <button
                type="button"
                onClick={onStartGame}
                disabled={!canStart}
                aria-label="Start the game"
                aria-disabled={!canStart}
              >
                Start Game
              </button>
            )}

            <button
              type="button"
              onClick={onLeave}
              aria-label="Leave the lobby and return to main menu"
            >
              Leave
            </button>
          </div>
        </section>
      )}
    </main>
  );
};
