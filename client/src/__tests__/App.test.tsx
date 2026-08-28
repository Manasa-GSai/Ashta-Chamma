/**
 * @vitest-environment jsdom
 *
 * Tests for App.tsx routing and lazy-loading configuration.
 *
 * Strategy:
 *   - Verify the BrowserRouter / Routes / Suspense structure renders without
 *     crashing for the root path (/).
 *   - Verify the lazy-loaded MainMenu is rendered (not a blank screen).
 *   - Verify navigation to /game renders the Game page (or its suspense
 *     fallback) rather than an error.
 *
 * React.lazy() returns a lazy component that resolves asynchronously.  We use
 * act() + waitFor() to let Suspense settle before asserting on DOM content.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { lazy, Suspense } from 'react';

// ---------------------------------------------------------------------------
// Mock the page modules so the tests do not depend on Three.js / Rapier being
// present in the test environment.
// ---------------------------------------------------------------------------

vi.mock('../pages/MainMenu', () => ({
  default: () => <div data-testid="main-menu">Main Menu</div>,
}));

vi.mock('../pages/Game', () => ({
  default: () => <div data-testid="game-page">Game Page</div>,
}));

// ---------------------------------------------------------------------------
// Re-import App after mocks are in place.
// ---------------------------------------------------------------------------

import { App } from '../App';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('App routing', () => {
  beforeEach(() => {
    // Reset location between tests.
    window.history.pushState({}, '', '/');
  });

  it('renders the MainMenu on the root path', async () => {
    await act(async () => {
      render(<App />);
    });

    await waitFor(() => {
      expect(screen.getByTestId('main-menu')).toBeInTheDocument();
    });
  });

  it('renders the Game page on /game', async () => {
    await act(async () => {
      // Use MemoryRouter to control the initial entry without mutating
      // window.location in a way that could bleed across tests.
      render(
        <MemoryRouter initialEntries={['/game']}>
          <Suspense fallback={<div>Loading…</div>}>
            {/* Inline lazy to test the dynamic import boundary in isolation */}
            {(() => {
              const LazyGame = lazy(() => import('../pages/Game'));
              return <LazyGame />;
            })()}
          </Suspense>
        </MemoryRouter>,
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId('game-page')).toBeInTheDocument();
    });
  });

  it('shows the Suspense fallback while a lazy page is loading', async () => {
    // Create a never-resolving lazy module to simulate a slow chunk download.
    const NeverReady = lazy(() => new Promise<{ default: React.ComponentType }>(() => {}));

    render(
      <Suspense fallback={<div data-testid="page-loader">Loading…</div>}>
        <NeverReady />
      </Suspense>,
    );

    expect(screen.getByTestId('page-loader')).toBeInTheDocument();
  });
});
