import { lazy, Suspense } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

/**
 * Route-level code splitting via React.lazy().
 *
 * Each page is loaded only when its route is first visited.  This means:
 *   - MainMenu: loaded on initial page load (lightweight, no 3D deps).
 *   - Game:     loaded on demand when the user navigates to /game.
 *              Three.js + Rapier are bundled into vendor-three / vendor-rapier
 *              chunks and downloaded only at that point.
 *
 * Splitting at the route boundary prevents any flash of unstyled content
 * because the Suspense fallback is shown during the chunk download rather than
 * an intermediate partially-rendered state.
 */
const MainMenu = lazy(() => import('./pages/MainMenu'));
const Game = lazy(() => import('./pages/Game'));

/**
 * Full-viewport loading indicator used as the Suspense fallback.
 *
 * Kept intentionally minimal (no external CSS) so it renders immediately
 * without waiting for any additional resources, avoiding a blank-screen flash.
 */
const PageLoader = (): JSX.Element => (
  <div
    style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100vh',
      fontFamily: 'system-ui, sans-serif',
    }}
    role="status"
    aria-live="polite"
  >
    Loading…
  </div>
);

/**
 * Root application component.
 *
 * BrowserRouter is the single history provider.  All route definitions live
 * here so the lazy() calls and the corresponding Suspense boundary are
 * co-located for easy code-splitting review.
 */
export const App = (): JSX.Element => {
  const [page, setPage] = useState<AppPage>('menu');

  if (page === 'lobby') {
    return (
      <Lobby
        players={[]}
        isHost={true}
        isReady={false}
        canStart={false}
        onCreateRoom={() => {
          /* room creation wired in by the game-session WO */
        }}
        onJoinRoom={() => {
          /* join logic wired in by the game-session WO */
        }}
        onToggleReady={() => {
          /* ready-toggle wired in by the game-session WO */
        }}
        onStartGame={() => {
          /* start-game wired in by the game-session WO */
        }}
        onLeave={() => setPage('menu')}
      />
    );
  }

  return (
    <BrowserRouter>
      {/*
       * Single Suspense boundary wraps all routes.  A per-route boundary would
       * give finer-grained loading states but a single boundary is sufficient
       * here and avoids duplicating the fallback UI.
       */}
      <Suspense fallback={<PageLoader />}>
        <Routes>
          <Route path="/" element={<MainMenu />} />
          <Route path="/game" element={<Game />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
};
