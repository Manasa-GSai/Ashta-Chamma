import { useState, useEffect, useCallback } from 'react';
import { ApiError, apiFetch } from '../lib/api';
import { t } from '../lib/i18n';
import styles from './Leaderboard.module.css';

export type Period = 'week' | 'month' | 'all';

export interface LeaderboardEntry {
  rank: number;
  user_id: string;
  display_name: string;
  total_wins: number;
  total_games: number;
}

interface LeaderboardProps {
  /** Clerk user ID of the currently authenticated user, used to highlight their row. */
  currentUserId?: string | null;
}

const PERIODS: ReadonlyArray<{ key: Period; labelKey: string }> = [
  { key: 'week', labelKey: 'leaderboard.filter.week' },
  { key: 'month', labelKey: 'leaderboard.filter.month' },
  { key: 'all', labelKey: 'leaderboard.filter.all' },
];

export const Leaderboard = ({ currentUserId }: LeaderboardProps): JSX.Element => {
  const [period, setPeriod] = useState<Period>('all');
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLeaderboard = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      // Auth is optional for leaderboard — no token passed
      const data = await apiFetch<LeaderboardEntry[]>(
        `/api/scores/leaderboard?period=${period}&limit=50`,
      );
      setEntries(data);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error.title'));
    } finally {
      setIsLoading(false);
    }
  }, [period]);

  useEffect(() => {
    void fetchLeaderboard();
  }, [fetchLeaderboard]);

  return (
    <section className={styles.container}>
      <h1 className={styles.title}>{t('leaderboard.title')}</h1>

      <div className={styles.filters} role="group" aria-label={t('leaderboard.title')}>
        {PERIODS.map(({ key, labelKey }) => (
          <button
            key={key}
            className={`${styles.filterBtn}${period === key ? ` ${styles.active}` : ''}`}
            onClick={() => { setPeriod(key); }}
            aria-pressed={period === key}
          >
            {t(labelKey)}
          </button>
        ))}
      </div>

      {isLoading && (
        <p className={styles.status} role="status" aria-live="polite">
          {t('common.loading')}
        </p>
      )}

      {!isLoading && error !== null && (
        <div className={styles.error} role="alert">
          <p>{error}</p>
          <button onClick={() => { void fetchLeaderboard(); }}>
            {t('common.error.retry')}
          </button>
        </div>
      )}

      {!isLoading && error === null && entries.length === 0 && (
        <p className={styles.status}>{t('leaderboard.empty')}</p>
      )}

      {!isLoading && error === null && entries.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{t('leaderboard.table.rank')}</th>
              <th scope="col">{t('leaderboard.table.player')}</th>
              <th scope="col">{t('leaderboard.table.wins')}</th>
              <th scope="col">{t('leaderboard.table.games')}</th>
              <th scope="col">{t('leaderboard.table.winRate')}</th>
            </tr>
          </thead>
          <tbody>
            {entries.map((entry) => {
              const isCurrentUser =
                currentUserId != null && entry.user_id === currentUserId;
              const winRate =
                entry.total_games > 0
                  ? Math.round((entry.total_wins / entry.total_games) * 100)
                  : 0;
              return (
                <tr
                  key={entry.user_id}
                  className={isCurrentUser ? styles.currentUser : undefined}
                  aria-current={isCurrentUser ? 'true' : undefined}
                >
                  <td>{entry.rank}</td>
                  <td>
                    {entry.display_name}
                    {isCurrentUser && (
                      <span className={styles.youBadge}> {t('leaderboard.you')}</span>
                    )}
                  </td>
                  <td>{entry.total_wins}</td>
                  <td>{entry.total_games}</td>
                  <td>{winRate}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
};
