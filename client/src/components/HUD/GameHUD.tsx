import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import { api } from '../../api/client';
import { useGameStore } from '../../store/gameStore';
import { PlayerList } from './PlayerList';
import { TurnIndicator } from './TurnIndicator';

const styles = {
  overlay: {
    position: 'absolute' as const,
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    pointerEvents: 'none' as const,
    display: 'flex',
    flexDirection: 'column' as const,
    justifyContent: 'space-between',
    padding: '1rem',
    zIndex: 10,
  },
  panel: {
    pointerEvents: 'auto' as const,
    maxWidth: '220px',
    width: '100%',
  },
  topRight: {
    display: 'flex',
    justifyContent: 'flex-end',
  },
  exitButton: {
    pointerEvents: 'auto' as const,
    padding: '0.5rem 1.25rem',
    backgroundColor: 'rgba(180,40,40,0.85)',
    color: '#fff',
    border: '1px solid rgba(255,100,100,0.5)',
    borderRadius: '8px',
    cursor: 'pointer',
    fontSize: '0.9rem',
    fontWeight: '600',
    fontFamily: "'Georgia', serif",
  },
  exitButtonDisabled: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
  exitError: {
    color: '#e08080',
    fontSize: '0.8rem',
    marginTop: '0.4rem',
    textAlign: 'right' as const,
    pointerEvents: 'auto' as const,
    textShadow: '0 1px 2px rgba(0,0,0,0.8)',
  },
  bottomRight: {
    display: 'flex',
    flexDirection: 'column' as const,
    alignItems: 'flex-end',
  },
} as const;

export const GameHUD = (): JSX.Element => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { roomCode, players, currentPlayerIndex, lastRollResult, reset } =
    useGameStore();

  const [isExiting, setIsExiting] = useState<boolean>(false);
  const [exitError, setExitError] = useState<string | null>(null);

  const currentPlayer = players[currentPlayerIndex] ?? null;

  const handleExit = async (): Promise<void> => {
    setExitError(null);
    setIsExiting(true);

    try {
      if (roomCode !== null) {
        await api.delete(`/api/rooms/${roomCode}/leave`);
      }
      reset();
      void navigate('/lobby');
    } catch {
      setExitError(t('hud.exit_error'));
      setIsExiting(false);
    }
  };

  return (
    <div style={styles.overlay} role="complementary" aria-label="Game HUD">
      {/* Top-left: Turn indicator */}
      <div style={styles.panel}>
        <TurnIndicator
          currentPlayer={currentPlayer}
          lastRollResult={lastRollResult}
        />
      </div>

      {/* Top-right: Exit button */}
      <div style={styles.topRight}>
        <div>
          <button
            style={{
              ...styles.exitButton,
              ...(isExiting ? styles.exitButtonDisabled : {}),
            }}
            onClick={() => void handleExit()}
            disabled={isExiting}
            type="button"
          >
            {isExiting ? t('hud.exit_loading') : t('hud.exit')}
          </button>
          {exitError !== null && (
            <p style={styles.exitError} role="alert">
              {exitError}
            </p>
          )}
        </div>
      </div>

      {/* Bottom-right: Player list */}
      <div style={styles.bottomRight}>
        <div style={styles.panel}>
          <PlayerList
            players={players}
            currentPlayerIndex={currentPlayerIndex}
          />
        </div>
      </div>
    </div>
  );
};
