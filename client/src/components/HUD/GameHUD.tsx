import { type JSX } from 'react';
import { useGameStore } from '../../store/gameStore';

export const GameHUD = (): JSX.Element => {
  const currentPlayer = useGameStore((state) => state.currentPlayer);
  const rollResult = useGameStore((state) => state.rollResult);
  const players = useGameStore((state) => state.players);

  const playerName = players[currentPlayer] ?? `Player ${currentPlayer + 1}`;

  return (
    <div className="game-hud">
      <div data-testid="current-player" className="hud-current-player">
        Current Player: {playerName}
      </div>
      {rollResult !== null && (
        <div data-testid="roll-result" className="hud-roll-result">
          Roll Result: {rollResult}
        </div>
      )}
    </div>
  );
};
