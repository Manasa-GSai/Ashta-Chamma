import { Link } from 'react-router-dom';

/**
 * Main menu / landing page.
 *
 * This component is intentionally lightweight — Three.js and Rapier are NOT
 * imported here so they never appear in the critical-path bundle that the
 * browser must parse before showing this screen.  The Lighthouse performance
 * score is measured against this route, so keeping it thin is essential for
 * meeting the ≥85 target.
 */
const MainMenu = (): JSX.Element => {
  return (
    <main
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        fontFamily: 'system-ui, sans-serif',
      }}
    >
      <h1>Ashta Chamma 3D</h1>
      <p>An ancient Indian board game, reimagined in 3D.</p>
      <nav style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
        <Link to="/game">
          <button type="button">Play</button>
        </Link>
        <Link to="/leaderboard">
          <button type="button">Leaderboard</button>
        </Link>
      </nav>
    </main>
  );
};

export default MainMenu;
