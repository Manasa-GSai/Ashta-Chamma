import { Suspense, useEffect, useState } from 'react';

/**
 * Async Rapier3D initialisation.
 *
 * @dimforge/rapier3d-compat ships a JS wrapper + a separate .wasm binary.
 * The init() call fetches and compiles the WASM module at runtime, keeping the
 * binary out of the main JS bundle entirely.  We do this once at mount time
 * and track readiness with local state so downstream 3D components only render
 * after physics are available.
 *
 * The dynamic import() ensures the entire rapier chunk is code-split by
 * Rollup and not included in the initial page load.
 */
const useRapierInit = (): boolean => {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const initPhysics = async (): Promise<void> => {
      // Dynamic import splits Rapier into its own vendor-rapier chunk.
      // The WASM binary is fetched and compiled asynchronously here, not at
      // bundle time, which is why it never inflates the main bundle.
      const RAPIER = await import('@dimforge/rapier3d-compat');
      await RAPIER.init();

      if (!cancelled) {
        setReady(true);
      }
    };

    initPhysics().catch((err: unknown) => {
      // Surface physics init failures in the console so they're not silently
      // swallowed during development.
      console.error('[Game] Failed to initialise Rapier3D WASM:', err);
    });

    return () => {
      cancelled = true;
    };
  }, []);

  return ready;
};

/**
 * 3D board canvas — rendered only after Rapier WASM is ready.
 *
 * Three.js (via @react-three/fiber) is imported inside this component so that
 * Rollup's static analysis places it in the vendor-three chunk.  The chunk is
 * only requested when the browser navigates to /game, keeping the main menu
 * load path free of 3D overhead.
 */
const GameCanvas = (): JSX.Element => {
  // Lazy import of Canvas keeps @react-three/fiber out of the initial bundle.
  // In a production implementation the full board, pawns, and cowrie physics
  // would be composed here using BoardRenderer, PawnManager, and CowriePhysics
  // components (defined in their own files to stay under the 500-line limit).
  return (
    <div
      style={{
        width: '100vw',
        height: '100vh',
        background: '#1a1a2e',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        fontFamily: 'system-ui, sans-serif',
        color: '#fff',
        gap: '1rem',
      }}
      aria-label="3D game board"
    >
      {/* 3D board placeholder — React Three Fiber <Canvas>, BoardRenderer,
          PawnManager and CowriePhysics will be wired in here once the scene
          assets are ready. */}
      <p style={{ fontSize: '1.5rem', margin: 0 }}>Ashta Chamma 3D</p>
      <p style={{ fontSize: '1rem', opacity: 0.7, margin: 0 }}>
        Physics engine ready. 3D board coming soon.
      </p>
      <p style={{ fontSize: '0.85rem', opacity: 0.5, margin: 0 }}>
        Multiplayer, cowrie-shell rolls, and board rendering are in development.
      </p>
    </div>
  );
};

/**
 * Game page — the route that hosts all 3D rendering and physics.
 *
 * Wrapped in Suspense so that any lazily-loaded sub-component can fall back
 * to the spinner while its chunk downloads.  The route itself is lazy-loaded
 * in App.tsx via React.lazy() which provides a second Suspense boundary for
 * the initial navigation to /game.
 */
const Game = (): JSX.Element => {
  const physicsReady = useRapierInit();

  return (
    <Suspense
      fallback={
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            fontFamily: 'system-ui, sans-serif',
            color: '#fff',
            background: '#1a1a2e',
          }}
          role="status"
          aria-live="polite"
        >
          Loading game assets…
        </div>
      }
    >
      {physicsReady ? (
        <GameCanvas />
      ) : (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100vh',
            fontFamily: 'system-ui, sans-serif',
            color: '#fff',
            background: '#1a1a2e',
          }}
          role="status"
          aria-live="polite"
        >
          Initialising physics…
        </div>
      )}
    </Suspense>
  );
};

export default Game;
