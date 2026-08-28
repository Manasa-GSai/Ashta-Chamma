import { useState, useEffect } from 'react';
import { Leaderboard } from './pages/Leaderboard';
import { Profile } from './pages/Profile';
import { t } from './lib/i18n';

/**
 * Supported client-side routes driven by the URL hash.
 * Hash-based routing avoids a server-side catch-all while keeping
 * the /leaderboard and /profile routes bookmarkable.
 */
type Route = 'home' | 'leaderboard' | 'profile';

function parseRoute(hash: string): Route {
  const path = hash.replace(/^#\/?/, '');
  if (path === 'leaderboard') return 'leaderboard';
  if (path === 'profile') return 'profile';
  return 'home';
}

export const App = (): JSX.Element => {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));

  useEffect(() => {
    const handleHashChange = (): void => {
      setRoute(parseRoute(window.location.hash));
    };
    window.addEventListener('hashchange', handleHashChange);
    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, []);

  // Auth tokens will be managed by Clerk in subsequent work orders.
  // Read from localStorage as a placeholder until AuthProvider is wired.
  const token = window.localStorage.getItem('auth_token');
  const userId = window.localStorage.getItem('user_id');

  return (
    <div>
      <nav aria-label="Main navigation">
        <a href="#">{t('common.nav.home')}</a>
        {' | '}
        <a href="#leaderboard">{t('common.nav.leaderboard')}</a>
        {' | '}
        <a href="#profile">{t('common.nav.profile')}</a>
      </nav>

      {route === 'home' && (
        <main>
          <h1>Ashta Chamma 3D</h1>
          <p>Monorepo scaffold initialized. Game implementation coming soon.</p>
        </main>
      )}

      {route === 'leaderboard' && (
        <Leaderboard currentUserId={userId} />
      )}

      {route === 'profile' && (
        <Profile token={token} />
      )}
    </div>
  );
};
