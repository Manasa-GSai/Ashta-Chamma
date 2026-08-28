import { useTranslation } from 'react-i18next';
import type { Player } from '../../store/gameStore';

interface PlayerListProps {
  players: Player[];
  currentPlayerIndex: number;
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
    marginBottom: '0.6rem',
  },
  playerRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
    padding: '0.25rem 0',
  },
  colorDot: {
    width: '12px',
    height: '12px',
    borderRadius: '50%',
    flexShrink: 0,
    border: '1px solid rgba(255,255,255,0.3)',
  },
  playerName: {
    flex: 1,
    fontSize: '0.95rem',
    color: '#f5e6c8',
  },
  playerNameActive: {
    fontWeight: '700',
    color: '#f5c842',
  },
  statusBadge: {
    fontSize: '0.7rem',
    padding: '0.1rem 0.4rem',
    borderRadius: '4px',
  },
  connectedBadge: {
    backgroundColor: 'rgba(80,200,80,0.2)',
    color: '#80e080',
    border: '1px solid rgba(80,200,80,0.3)',
  },
  disconnectedBadge: {
    backgroundColor: 'rgba(200,80,80,0.2)',
    color: '#e08080',
    border: '1px solid rgba(200,80,80,0.3)',
  },
  aiBadge: {
    backgroundColor: 'rgba(100,100,200,0.2)',
    color: '#9090e0',
    border: '1px solid rgba(100,100,200,0.3)',
  },
} as const;

export const PlayerList = ({
  players,
  currentPlayerIndex,
}: PlayerListProps): JSX.Element => {
  const { t } = useTranslation();

  return (
    <div style={styles.container}>
      <p style={styles.label}>{t('hud.players')}</p>

      <ul aria-label={t('hud.players')} style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {players.map((player, index) => {
          const isActive = index === currentPlayerIndex;
          return (
            <li key={player.id} style={styles.playerRow}>
              <div
                style={{
                  ...styles.colorDot,
                  backgroundColor: player.color,
                }}
                aria-hidden="true"
              />
              <span
                style={{
                  ...styles.playerName,
                  ...(isActive ? styles.playerNameActive : {}),
                }}
              >
                {player.name}
              </span>

              {player.isAI ? (
                <span
                  style={{ ...styles.statusBadge, ...styles.aiBadge }}
                  aria-label={t('hud.ai_label')}
                >
                  {t('hud.ai_label')}
                </span>
              ) : (
                <span
                  style={{
                    ...styles.statusBadge,
                    ...(player.isConnected
                      ? styles.connectedBadge
                      : styles.disconnectedBadge),
                  }}
                  aria-label={
                    player.isConnected
                      ? t('hud.connected')
                      : t('hud.disconnected')
                  }
                >
                  {player.isConnected
                    ? t('hud.connected')
                    : t('hud.disconnected')}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
};
