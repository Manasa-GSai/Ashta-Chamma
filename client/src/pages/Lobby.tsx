import { useState, type JSX, type FormEvent, type ChangeEvent } from 'react';

interface LobbyProps {
  onJoin?: (code: string) => void;
}

// Room codes are exactly 6 uppercase alphanumeric characters
const ROOM_CODE_PATTERN = /^[A-Z0-9]{6}$/;
const VALIDATION_ERROR = 'Room code must be exactly 6 uppercase letters or digits (e.g. ABC123)';

export const Lobby = ({ onJoin }: LobbyProps): JSX.Element => {
  const [roomCode, setRoomCode] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    // Normalise to uppercase so users don't have to hold Shift
    setRoomCode(e.target.value.toUpperCase());
  };

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!ROOM_CODE_PATTERN.test(roomCode)) {
      setError(VALIDATION_ERROR);
      return;
    }
    setError(null);
    onJoin?.(roomCode);
  };

  return (
    <div className="lobby">
      <h2>Join a Room</h2>
      <form onSubmit={handleSubmit} noValidate>
        <label htmlFor="roomCode">Room Code</label>
        <input
          id="roomCode"
          type="text"
          value={roomCode}
          onChange={handleChange}
          placeholder="Enter 6-character room code"
          maxLength={6}
          autoComplete="off"
          aria-describedby={error ? 'roomCode-error' : undefined}
        />
        {error !== null && (
          <p id="roomCode-error" role="alert">
            {error}
          </p>
        )}
        <button type="submit">Join Room</button>
      </form>
    </div>
  );
};
