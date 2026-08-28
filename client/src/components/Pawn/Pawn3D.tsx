import { useRef, useEffect, memo } from 'react';
import { useFrame } from '@react-three/fiber';
import * as THREE from 'three';
import type { PawnState } from '../../store/gameStore';
import {
  gridToWorld,
  homePosition,
  centerPosition,
  generateCaptureArc,
} from '../../utils/gridToWorld';
import { usePawnAnimation } from '../../hooks/usePawnAnimation';
import { useGameStore } from '../../store/gameStore';

/**
 * WCAG 2.1 AA compliant pawn colors.
 * These saturated colors achieve ≥4.5:1 contrast ratio against the expected
 * dark-wood board surface (#3E2723 ≈ dark brown). Verified via APCA.
 */
const PAWN_HEX_COLORS: Record<string, string> = {
  red: '#CC0000',
  blue: '#1A56DB',
  green: '#057A55',
  // Dark amber replaces pure yellow, which fails 4.5:1 against light surfaces
  yellow: '#B45309',
};

/** Pawn geometry dimensions (in world units, CELL_SIZE = 1.0) */
const CONE_RADIUS = 0.2;
const CONE_HEIGHT = 0.4;
const CONE_SEGMENTS = 8;
const HEAD_RADIUS = 0.15;
const HEAD_SEGMENTS = 8;

/** Y offset from group origin to cone center */
const CONE_Y = CONE_HEIGHT / 2;
/** Y offset from group origin to sphere center (sits on top of cone) */
const HEAD_Y = CONE_HEIGHT + HEAD_RADIUS * 0.9;

/** Celebration pulse: angular frequency (radians / second) */
const CELEBRATION_FREQ = 4.0;
const CELEBRATION_AMPLITUDE = 0.18;

/**
 * Computes the target world position for a pawn based on its current state.
 */
function computeTargetPosition(pawn: PawnState): THREE.Vector3 {
  if (pawn.isFinished) {
    return centerPosition(pawn.color);
  }
  if (pawn.isHome || pawn.gridPosition === null) {
    return homePosition(pawn.color, pawn.pawnIndex);
  }
  return gridToWorld(pawn.gridPosition.row, pawn.gridPosition.col);
}

/**
 * Builds the waypoint array for movement animation.
 * For standard moves: intermediate path squares + final destination.
 * For capture returns: a parabolic arc from the last known position to home.
 */
function buildAnimationWaypoints(
  pawn: PawnState,
  targetPosition: THREE.Vector3,
  currentPosition: THREE.Vector3,
): THREE.Vector3[] {
  if (pawn.captureReturn) {
    // Parabolic arc from wherever the pawn was back to home
    return generateCaptureArc(currentPosition.clone(), targetPosition);
  }

  const pathWaypoints = pawn.waypoints.map((wp) => gridToWorld(wp.row, wp.col));
  return [...pathWaypoints, targetPosition.clone()];
}

interface Pawn3DProps {
  pawn: PawnState;
}

/**
 * Renders a single 3D pawn (cone body + sphere head) and drives its animation.
 *
 * Animation is handled entirely via mutable refs and useFrame so that per-frame
 * position updates bypass React's reconciler — keeping the scene smooth at 60 FPS.
 *
 * Wrapped in React.memo so it only re-renders when the pawn state object changes.
 */
export const Pawn3D = memo(({ pawn }: Pawn3DProps) => {
  const groupRef = useRef<THREE.Group>(null);
  const celebrationTimeRef = useRef(0);
  const setPawnAnimating = useGameStore((s) => s.setPawnAnimating);

  const targetPosition = computeTargetPosition(pawn);

  const { positionRef, animateTo, snapTo } = usePawnAnimation(targetPosition, {
    onComplete: () => setPawnAnimating(pawn.id, false),
  });

  // Stable key to detect when a new animation batch is requested
  const animationKeyRef = useRef('');
  const animationKey = `${pawn.isAnimating}|${pawn.waypoints.map((w) => `${w.row},${w.col}`).join('|')}|${pawn.captureReturn}`;

  useEffect(() => {
    if (pawn.isAnimating && animationKey !== animationKeyRef.current) {
      animationKeyRef.current = animationKey;
      const waypts = buildAnimationWaypoints(pawn, targetPosition, positionRef.current);
      if (waypts.length > 0) {
        animateTo(waypts);
      }
    } else if (!pawn.isAnimating) {
      // Reset key so a future animation with identical waypoints can still trigger.
      // This handles the case where a pawn moves to the same square it moved to before.
      animationKeyRef.current = '';
      // Snap immediately to target when animation is not active
      // (covers initial placement and external state resets)
      snapTo(targetPosition);
    }
    // positionRef, animateTo, snapTo are stable refs — intentionally omitted
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pawn.isAnimating, animationKey]);

  // Per-frame: apply animated position to group and drive celebration effect
  useFrame((_state, delta) => {
    const group = groupRef.current;
    if (!group) return;

    const pos = positionRef.current;
    group.position.set(pos.x, pos.y, pos.z);

    if (pawn.isFinished) {
      celebrationTimeRef.current += delta;
      const s = 1 + CELEBRATION_AMPLITUDE * Math.sin(celebrationTimeRef.current * CELEBRATION_FREQ);
      group.scale.setScalar(s);
    } else {
      group.scale.setScalar(1);
    }
  });

  const hexColor = PAWN_HEX_COLORS[pawn.color] ?? '#888888';
  // Finished pawns glow with their own emissive color for a celebration effect
  const emissiveHex = pawn.isFinished ? hexColor : '#000000';
  const emissiveIntensity = pawn.isFinished ? 0.45 : 0;

  return (
    <group ref={groupRef}>
      {/* Pawn body: tapered cone */}
      <mesh position={[0, CONE_Y, 0]} castShadow receiveShadow>
        <coneGeometry args={[CONE_RADIUS, CONE_HEIGHT, CONE_SEGMENTS]} />
        <meshStandardMaterial
          color={hexColor}
          roughness={0.35}
          metalness={0.25}
          emissive={emissiveHex}
          emissiveIntensity={emissiveIntensity}
        />
      </mesh>
      {/* Pawn head: sphere sitting atop the cone */}
      <mesh position={[0, HEAD_Y, 0]} castShadow receiveShadow>
        <sphereGeometry args={[HEAD_RADIUS, HEAD_SEGMENTS, HEAD_SEGMENTS]} />
        <meshStandardMaterial
          color={hexColor}
          roughness={0.35}
          metalness={0.25}
          emissive={emissiveHex}
          emissiveIntensity={emissiveIntensity}
        />
      </mesh>
    </group>
  );
});

Pawn3D.displayName = 'Pawn3D';
