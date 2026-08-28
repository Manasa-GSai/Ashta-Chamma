import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { JSX, Ref, RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import {
  Physics,
  RigidBody,
  BallCollider,
  CuboidCollider,
  useRapier,
} from '@react-three/rapier';
import type { RapierRigidBody } from '@react-three/rapier';
import * as THREE from 'three';
import { CowrieShell } from './CowrieShell';
import { usePhysicsSettle } from '../../hooks/usePhysicsSettle';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Number of cowrie shells in a standard Ashta Chamma throw. */
const SHELL_COUNT = 4;

/**
 * Staggered starting positions above the ground plane.
 * Shells are clustered near the centre so they land in the visible throw area.
 */
const INITIAL_POSITIONS: ReadonlyArray<[number, number, number]> = [
  [-0.2, 1.5, -0.15],
  [0.2, 1.7, -0.1],
  [-0.15, 1.9, 0.15],
  [0.1, 2.1, 0.2],
] as const;

/**
 * Shell orientation quaternions.
 *
 * Default mesh orientation: dome faces +Y (mouth-down).
 * Mouth-up = flip 180° around the local X axis so the flat ventral face faces +Y.
 */
const MOUTH_DOWN_QUAT = new THREE.Quaternion(); // identity — dome up
const MOUTH_UP_QUAT = new THREE.Quaternion().setFromEuler(new THREE.Euler(Math.PI, 0, 0));

/**
 * Speed of the slerp lerp from settled physics rotation to the server-provided
 * final orientation. Higher = snappier, lower = smoother.
 */
const LERP_SPEED = 4.0; // effective "multiplier per second" for slerp

/**
 * Animation phase state machine:
 *
 *  idle → rolling → lerping → done
 *           ↑                   |
 *           └── (new rollTrigger) ──┘
 */
type AnimPhase = 'idle' | 'rolling' | 'lerping' | 'done';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CowriePhysicsProps {
  /**
   * Server-provided roll result: index i is true when shell i should settle
   * mouth-up.  Four values are expected (one per shell).  Pass null before the
   * first roll or while waiting for the server response.
   */
  rollResult: boolean[] | null;
  /**
   * Increment this counter to trigger a new throw animation.
   * The component reacts to any change away from 0 by launching all shells.
   */
  rollTrigger: number;
  /**
   * Called once after shells have settled AND their orientations have been lerped
   * to match the server-provided `rollResult`.
   */
  onSettled: () => void;
}

// ---------------------------------------------------------------------------
// Inner scene (must live inside <Physics> to use Rapier hooks)
// ---------------------------------------------------------------------------

const CowriePhysicsScene = ({
  rollResult,
  rollTrigger,
  onSettled,
}: CowriePhysicsProps): JSX.Element => {
  // ---- Rigid body refs ----
  const shell0Ref = useRef<RapierRigidBody | null>(null);
  const shell1Ref = useRef<RapierRigidBody | null>(null);
  const shell2Ref = useRef<RapierRigidBody | null>(null);
  const shell3Ref = useRef<RapierRigidBody | null>(null);

  // Stable array of refs — identity never changes so it is safe to use as a
  // dependency in hooks without triggering spurious re-runs.
  const shellRefs = useMemo(
    () =>
      [shell0Ref, shell1Ref, shell2Ref, shell3Ref] as Array<
        RefObject<RapierRigidBody | null>
      >,
    [],
  );

  // ---- Animation state ----
  const [phase, setPhase] = useState<AnimPhase>('idle');
  const prevRollTrigger = useRef(0);
  const lerpProgress = useRef(0);
  const onSettledRef = useRef(onSettled);
  onSettledRef.current = onSettled; // keep ref current without adding to deps

  // Rapier namespace (needed for RigidBodyType enum when switching to kinematic).
  const { rapier } = useRapier();

  // ---- Throw impulse ----
  useEffect(() => {
    if (rollTrigger === 0 || rollTrigger === prevRollTrigger.current) return;
    prevRollTrigger.current = rollTrigger;

    // Reset phase so settle detection starts fresh.
    setPhase('rolling');
    lerpProgress.current = 0;

    shellRefs.forEach((ref, i) => {
      const body = ref.current;
      if (!body) return;

      // Teleport shell back to its starting position so repeated throws look
      // identical in terms of starting location.
      const pos = INITIAL_POSITIONS[i];
      body.setTranslation({ x: pos[0], y: pos[1], z: pos[2] }, true);
      body.setRotation({ x: 0, y: 0, z: 0, w: 1 }, true);
      body.setLinvel({ x: 0, y: 0, z: 0 }, true);
      body.setAngvel({ x: 0, y: 0, z: 0 }, true);

      // Wake the body in case it was sleeping, then apply randomised throw.
      body.wakeUp();

      // Upward + lateral impulse — shells are very light (mass ≈ 0.08 kg).
      body.applyImpulse(
        {
          x: (Math.random() - 0.5) * 0.12,
          y: 0.28 + Math.random() * 0.18,
          z: (Math.random() - 0.5) * 0.12,
        },
        true,
      );

      // Random torque so each shell tumbles independently.
      body.applyTorqueImpulse(
        {
          x: (Math.random() - 0.5) * 0.25,
          y: (Math.random() - 0.5) * 0.25,
          z: (Math.random() - 0.5) * 0.25,
        },
        true,
      );
    });
  }, [rollTrigger, shellRefs]);

  // ---- Settle detection callback ----
  const handlePhysicsSettled = useCallback(() => {
    // Switch every shell to kinematic-position so physics stops fighting us
    // during the orientation lerp.
    shellRefs.forEach((ref) => {
      const body = ref.current;
      if (!body) return;
      // KinematicPositionBased = 2 in the Rapier enum.
      body.setBodyType(rapier.RigidBodyType.KinematicPositionBased, true);
    });

    lerpProgress.current = 0;
    setPhase('lerping');
  }, [shellRefs, rapier]);

  // forceSettle is used by the settle hook internally (timeout path); we do
  // not expose it on the public API but retaining the destructure lets us
  // add abort-throw support later without changing the hook contract.
  usePhysicsSettle({
    rigidBodyRefs: shellRefs,
    isActive: phase === 'rolling',
    onSettled: handlePhysicsSettled,
  });

  // ---- Orientation lerp ----
  useFrame((_state, delta) => {
    if (phase !== 'lerping') return;

    // Advance lerp progress (clamped to [0, 1]).
    lerpProgress.current = Math.min(1.0, lerpProgress.current + delta * LERP_SPEED);
    const t = lerpProgress.current;

    shellRefs.forEach((ref, i) => {
      const body = ref.current;
      if (!body) return;

      // Use server result when available, otherwise default to mouth-down.
      const targetQuat =
        rollResult !== null && rollResult[i] === true ? MOUTH_UP_QUAT : MOUTH_DOWN_QUAT;

      const currentRot = body.rotation();
      const current = new THREE.Quaternion(
        currentRot.x,
        currentRot.y,
        currentRot.z,
        currentRot.w,
      );
      current.slerp(targetQuat, t);

      body.setNextKinematicRotation({
        x: current.x,
        y: current.y,
        z: current.z,
        w: current.w,
      });
    });

    if (lerpProgress.current >= 1.0) {
      setPhase('done');
      onSettledRef.current();
    }
  });

  // ---- Render ----
  return (
    <>
      {/* Ambient + directional lighting for the throw area */}
      <ambientLight intensity={0.6} />
      <directionalLight
        position={[4, 8, 4]}
        intensity={1.2}
        castShadow
        shadow-mapSize={[512, 512]}
      />

      {/* Ground plane — fixed rigid body for shells to land on */}
      <RigidBody type="fixed" name="ground">
        <mesh
          rotation={[-Math.PI / 2, 0, 0]}
          receiveShadow
        >
          <planeGeometry args={[8, 8]} />
          <meshStandardMaterial color="#c8a96e" roughness={0.8} />
        </mesh>
        <CuboidCollider args={[4, 0.05, 4]} position={[0, -0.05, 0]} />
      </RigidBody>

      {/* Four cowrie shells with independent rigid bodies */}
      {(INITIAL_POSITIONS as Array<[number, number, number]>).map((pos, i) => {
        const shellRef = shellRefs[i];
        return (
          <RigidBody
            key={i}
            ref={shellRef as Ref<RapierRigidBody>}
            position={pos}
            colliders={false}
            mass={0.08}
            restitution={0.25}
            friction={0.85}
            linearDamping={0.35}
            angularDamping={0.55}
            ccd
            name={`cowrie-shell-${i}`}
          >
            {/*
             * BallCollider approximates the shell's roughly oval silhouette.
             * Using a sphere keeps physics cheap (O(1) collision vs mesh).
             */}
            <BallCollider args={[0.12]} />
            <CowrieShell />
          </RigidBody>
        );
      })}
    </>
  );
};

// ---------------------------------------------------------------------------
// Public component
// ---------------------------------------------------------------------------

/**
 * CowriePhysics renders a Rapier3D physics simulation of four cowrie shells
 * being thrown and settling to rest.
 *
 * The component must be rendered inside a `<Canvas>` from `@react-three/fiber`.
 * It manages its own `<Physics>` world so it can be dropped anywhere in the
 * React Three Fiber scene graph.
 *
 * Usage:
 * ```tsx
 * <Canvas>
 *   <Suspense fallback={null}>
 *     <CowriePhysics
 *       rollResult={[true, false, true, false]}
 *       rollTrigger={throwCount}
 *       onSettled={() => setRolling(false)}
 *     />
 *   </Suspense>
 * </Canvas>
 * ```
 *
 * @param rollResult  4-element boolean array from server: true = mouth-up.
 * @param rollTrigger Increment to launch a new throw.
 * @param onSettled   Fires once shells reach their final orientations.
 */
export const CowriePhysics = (props: CowriePhysicsProps): JSX.Element => {
  return (
    /*
     * Suspense is required because Rapier3D loads its WASM binary lazily.
     * Wrapping here prevents the parent app from needing its own Suspense.
     */
    <Suspense fallback={null}>
      <Physics
        gravity={[0, -9.81, 0]}
        // Limit simulation substeps to maintain 60 FPS on mid-range devices.
        maxStabilizationIterations={4}
        maxVelocityFrictionIterations={8}
        maxVelocityIterations={4}
      >
        <CowriePhysicsScene {...props} />
      </Physics>
    </Suspense>
  );
};

// Re-export SHELL_COUNT so consumers can build rollResult arrays correctly.
export { SHELL_COUNT };
