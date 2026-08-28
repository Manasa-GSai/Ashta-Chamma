import { useTranslation } from 'react-i18next';
import type { Player } from '../../store/gameStore';

interface TurnIndicatorProps {
  currentPlayer: Player | null;
  lastRollResult: number | null;
}

const styles = {
  container: {
    backgroundColor: 'rgba(0,0,0,0.75)',
    borderRadius: '10px',
    padding: '0.75rem 1rem',
    marginBottom: '0.75rem',
    border: '1px solid rgba(245,200,66,0.3)',
  },
  label: {
    fontSize: '0.75rem',
    color: '#aaa',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
    marginBottom: '0.4rem',
  },
  playerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  colorDot: {
    width: '14px',
    height: '14px',
    borderRadius: '50%',
    flexShrink: 0,
    border: '1px solid rgba(255,255,255,0.3)',
  },
  playerName: {
    fontSize: '1.1rem',
    fontWeight: '700',
    color: '#f5e6c8',
  },
  rollRow: {
    marginTop: '0.5rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  rollLabel: {
    fontSize: '0.75rem',
    color: '#aaa',
    textTransform: 'uppercase' as const,
    letterSpacing: '0.05em',
  },
  rollValue: {
    fontSize: '1.4rem',
    fontWeight: '700',
    color: '#f5c842',
  },
} as const;

export const TurnIndicator = ({
  currentPlayer,
  lastRollResult,
}: TurnIndicatorProps): JSX.Element => {
  const { t } = useTranslation();

  return (
    <div style={styles.container} role="status" aria-live="polite">
      <p style={styles.label}>{t('hud.current_turn')}</p>

      <div style={styles.playerRow}>
        <div
          style={{
            ...styles.colorDot,
            backgroundColor: currentPlayer?.color ?? '#888',
          }}
          aria-hidden="true"
        />
        <span style={styles.playerName}>
          {currentPlayer?.name ?? '—'}
        </span>
      </div>

      <div style={styles.rollRow}>
        <span style={styles.rollLabel}>{t('hud.last_roll')}</span>
        <span style={styles.rollValue}>
          {lastRollResult !== null ? String(lastRollResult) : t('hud.no_roll')}
        </span>
      </div>
    </div>
  );
};
