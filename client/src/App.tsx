import { Suspense, useState } from 'react';
import type { JSX } from 'react';
import { Canvas } from '@react-three/fiber';
import { CowriePhysics, SHELL_COUNT } from './components/Cowrie/CowriePhysics';

/**
 * Demo of the CowriePhysics component.
 *
 * In production the roll trigger and roll result come from the WebSocket
 * client (WO-028); here they are simulated locally so the animation can be
 * previewed standalone.
 */
export const App = (): JSX.Element => {
  const [rollTrigger, setRollTrigger] = useState(0);
  const [rollResult, setRollResult] = useState<boolean[] | null>(null);
  const [isRolling, setIsRolling] = useState(false);
  const [settleSummary, setSettleSummary] = useState<string | null>(null);

  const handleRoll = () => {
    // Simulate a server roll result: random mouth-up/down for each shell.
    const result = Array.from({ length: SHELL_COUNT }, () => Math.random() > 0.5);
    setRollResult(result);
    setIsRolling(true);
    setSettleSummary(null);
    setRollTrigger((n) => n + 1);
  };

  const handleSettled = () => {
    setIsRolling(false);
    if (rollResult !== null) {
      const mouthUp = rollResult.filter(Boolean).length;
      setSettleSummary(`Roll settled — ${mouthUp} mouth-up`);
    }
  };

  return (
    <main style={{ width: '100vw', height: '100vh', background: '#1a1006' }}>
      {/* 3D viewport */}
      <Canvas
        camera={{ position: [0, 2.5, 3.5], fov: 45 }}
        shadows
        style={{ width: '100%', height: '80vh' }}
      >
        <Suspense fallback={null}>
          <CowriePhysics
            rollResult={rollResult}
            rollTrigger={rollTrigger}
            onSettled={handleSettled}
          />
        </Suspense>
      </Canvas>

      {/* HUD overlay */}
      <div
        style={{
          position: 'absolute',
          bottom: 24,
          left: '50%',
          transform: 'translateX(-50%)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 8,
        }}
      >
        <button
          onClick={handleRoll}
          disabled={isRolling}
          style={{
            padding: '12px 32px',
            fontSize: 18,
            fontWeight: 600,
            borderRadius: 8,
            border: 'none',
            background: isRolling ? '#555' : '#d4881a',
            color: '#fff',
            cursor: isRolling ? 'not-allowed' : 'pointer',
          }}
        >
          {isRolling ? 'Rolling…' : 'Roll Cowries'}
        </button>

        {settleSummary !== null && (
          <p style={{ color: '#e8d5a8', margin: 0 }}>{settleSummary}</p>
        )}
      </div>
    </main>
  );
};
