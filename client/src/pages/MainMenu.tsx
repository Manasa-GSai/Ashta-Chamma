import { useNavigate } from 'react-router-dom';
import type { JSX } from 'react';

/**
 * Props for the pure MainMenu component.
 * Both handlers are optional so the component is safe to render in unit tests
 * without a router context — tests supply mocks; the router-aware wrapper
 * (default export) wires useNavigate in production.
 */
export interface MainMenuProps {
  onPlay?: () => void;
  onRules?: () => void;
}

/**
 * Pure presentation component — no router dependency.
 * Named export is used by unit tests and any consumer that wants to control
 * navigation externally.
 */
export const MainMenu = ({ onPlay, onRules }: MainMenuProps): JSX.Element => {
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
        <button type="button" onClick={onPlay}>
          Play
        </button>
        <button type="button" onClick={onRules}>
          Rules
        </button>
      </nav>
    </main>
  );
};

/**
 * Router-aware wrapper — the default export used by React.lazy() in App.tsx.
 * Wires onPlay/onRules to useNavigate so the pure component stays testable
 * without a BrowserRouter.
 */
const MainMenuRoute = (): JSX.Element => {
  const navigate = useNavigate();
  return (
    <MainMenu
      onPlay={() => navigate('/game')}
      onRules={() => navigate('/rules')}
    />
  );
};

export default MainMenuRoute;
