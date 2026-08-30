import { type JSX } from 'react';
import { useGameStore } from '../../store/gameStore';

export const GameHUD = (): JSX.Element => {
  const currentPlayerIndex = useGameStore((state) => state.currentPlayerIndex);
  const currentRoll = useGameStore((state) => state.currentRoll);
  const players = useGameStore((state) => state.players);

  const playerName =
    players[currentPlayerIndex]?.name ?? `Player ${currentPlayerIndex + 1}`;

  return (
    <div className="game-hud">
      <div data-testid="current-player" className="hud-current-player">
        Current Player: {playerName}
      </div>
      {currentRoll !== null && (
        <div data-testid="roll-result" className="hud-roll-result">
          Roll Result: {currentRoll}
        </div>
      )}
    </div>
  );
};
