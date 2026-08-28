import { useState, useEffect, useCallback } from 'react';
import { ApiError, apiFetch } from '../lib/api';
import { t } from '../lib/i18n';
import styles from './Profile.module.css';

interface UserProfile {
  id: string;
  display_name: string;
  avatar_url: string | null;
  locale: string;
}

export interface ScoreHistoryEntry {
  id: number;
  room_id: string;
  finish_position: number;
  pawns_captured: number;
  pawns_lost: number;
  duration_seconds: number;
  scored_at: string;
}

interface ProfileProps {
  /** JWT access token from Clerk; required to fetch profile data. */
  token?: string | null;
}

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m)}:${String(s).padStart(2, '0')}`;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export const Profile = ({ token }: ProfileProps): JSX.Element => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [history, setHistory] = useState<ScoreHistoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (token == null) {
      setError(t('profile.error.auth'));
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const [profileData, historyData] = await Promise.all([
        apiFetch<UserProfile>('/api/users/me', {}, token),
        apiFetch<ScoreHistoryEntry[]>('/api/scores/history', {}, token),
      ]);
      setProfile(profileData);
      setHistory(historyData);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error.title'));
    } finally {
      setIsLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void fetchData();
  }, [fetchData]);

  if (isLoading) {
    return (
      <section className={styles.container}>
        <p className={styles.status} role="status" aria-live="polite">
          {t('common.loading')}
        </p>
      </section>
    );
  }

  if (error !== null) {
    return (
      <section className={styles.container}>
        <div className={styles.error} role="alert">
          <p>{error}</p>
          {token != null && (
            <button onClick={() => { void fetchData(); }}>
              {t('common.error.retry')}
            </button>
          )}
        </div>
      </section>
    );
  }

  return (
    <section className={styles.container}>
      <h1 className={styles.title}>{t('profile.title')}</h1>

      {profile !== null && (
        <div className={styles.profileCard}>
          {profile.avatar_url !== null && (
            <img
              src={profile.avatar_url}
              alt={profile.display_name}
              className={styles.avatar}
            />
          )}
          <p className={styles.displayName}>{profile.display_name}</p>
        </div>
      )}

      <h2 className={styles.sectionTitle}>{t('profile.history.title')}</h2>

      {history.length === 0 ? (
        <p className={styles.status}>{t('profile.history.empty')}</p>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col">{t('profile.history.date')}</th>
              <th scope="col">{t('profile.history.result')}</th>
              <th scope="col">{t('profile.history.duration')}</th>
              <th scope="col">{t('profile.history.captured')}</th>
            </tr>
          </thead>
          <tbody>
            {history.map((entry) => {
              const isWin = entry.finish_position === 1;
              return (
                <tr key={entry.id}>
                  <td>{formatDate(entry.scored_at)}</td>
                  <td className={isWin ? styles.win : styles.loss}>
                    {isWin ? t('profile.result.win') : t('profile.result.loss')}
                  </td>
                  <td>{formatDuration(entry.duration_seconds)}</td>
                  <td>{entry.pawns_captured}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </section>
  );
};
