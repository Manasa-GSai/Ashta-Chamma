import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { Board3D } from './Board3D';

/**
 * Main R3F scene for the Ashta Chamma 3D board.
 *
 * Camera is positioned at an angled top-down view (y=12, z=8) with
 * a 50° FOV that shows the entire cross-shaped board. OrbitControls
 * allow the user to rotate and zoom without panning off the board.
 *
 * Lighting:
 *  - AmbientLight (intensity 0.5) provides base illumination.
 *  - DirectionalLight (intensity 0.8) casts shadows for depth perception.
 *
 * Performance:
 *  - Board3D is memoised; cells are computed once via useMemo.
 *  - Shadow map is 1024×1024 — sufficient quality for a static board.
 */
export const BoardScene = (): JSX.Element => {
  return (
    <div
      style={{ width: '100%', height: '100vh', background: '#1a1a2e' }}
      data-testid="board-scene-container"
    >
      <Canvas
        shadows
        camera={{ position: [0, 12, 8], fov: 50, near: 0.1, far: 100 }}
        gl={{ antialias: true }}
      >
        {/* Base illumination — keeps dark areas visible */}
        <ambientLight intensity={0.5} />

        {/* Main directional light for depth and shadows */}
        <directionalLight
          position={[5, 10, 5]}
          intensity={0.8}
          castShadow
          shadow-mapSize-width={1024}
          shadow-mapSize-height={1024}
          shadow-camera-near={0.5}
          shadow-camera-far={50}
          shadow-camera-left={-12}
          shadow-camera-right={12}
          shadow-camera-top={12}
          shadow-camera-bottom={-12}
        />

        {/* The 45-square cross-shaped board */}
        <Board3D />

        {/* Orbit controls — polar angle clamped to prevent flipping */}
        <OrbitControls
          enablePan={false}
          minPolarAngle={Math.PI / 6}
          maxPolarAngle={Math.PI / 2.2}
          minDistance={8}
          maxDistance={24}
        />
      </Canvas>
    </div>
  );
};
