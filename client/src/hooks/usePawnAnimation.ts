import { useRef, useCallback } from 'react';
import { useFrame } from '@react-three/fiber';
import { Vector3 } from 'three';

/**
 * World-units per second the pawn travels along its path.
 * At CELL_SIZE=1, an 8-square move (8 units) completes in ~0.8s, within the 1s budget.
 */
const ANIMATION_SPEED = 10.0;

/** Distance threshold at which we snap to the current waypoint and advance */
const ARRIVAL_THRESHOLD = 0.025;

export interface UsePawnAnimationOptions {
  /** Called once when all waypoints have been reached */
  onComplete?: () => void;
}

export interface UsePawnAnimationResult {
  /**
   * Mutable ref holding the pawn's current animated world position.
   * Apply this to a Three.js Group each frame via useFrame.
   */
  positionRef: React.MutableRefObject<Vector3>;
  /**
   * Mutable ref indicating whether animation is currently running.
   * Read this to check state without causing re-renders.
   */
  isAnimatingRef: React.MutableRefObject<boolean>;
  /**
   * Begin animating through the supplied ordered waypoints.
   * Replaces any in-progress animation.
   */
  animateTo: (waypoints: Vector3[]) => void;
  /**
   * Instantly teleport to a position without animation.
   * Use this for initial placement or when isAnimating is false.
   */
  snapTo: (position: Vector3) => void;
}

/**
 * Hook that drives smooth lerp-based position animation for a pawn.
 * Must be used inside a React Three Fiber Canvas context (uses `useFrame`).
 *
 * Design: positions are tracked in a mutable ref so that each frame's
 * mutation does not trigger a React re-render — only the Three.js scene
 * graph is mutated, keeping animation smooth at 60 FPS.
 */
export function usePawnAnimation(
  initialPosition: Vector3,
  options: UsePawnAnimationOptions = {},
): UsePawnAnimationResult {
  const positionRef = useRef<Vector3>(initialPosition.clone());
  const waypointsRef = useRef<Vector3[]>([]);
  const waypointIndexRef = useRef<number>(0);
  const isAnimatingRef = useRef<boolean>(false);

  // Keep onComplete stable without stale closure issues
  const onCompleteRef = useRef(options.onComplete);
  onCompleteRef.current = options.onComplete;

  const animateTo = useCallback((waypoints: Vector3[]) => {
    if (waypoints.length === 0) return;
    // Clone to avoid external mutation affecting in-flight animation
    waypointsRef.current = waypoints.map((v) => v.clone());
    waypointIndexRef.current = 0;
    isAnimatingRef.current = true;
  }, []);

  const snapTo = useCallback((position: Vector3) => {
    positionRef.current.copy(position);
    isAnimatingRef.current = false;
    waypointsRef.current = [];
    waypointIndexRef.current = 0;
  }, []);

  useFrame((_state, delta) => {
    if (!isAnimatingRef.current) return;

    const waypoints = waypointsRef.current;
    const idx = waypointIndexRef.current;

    if (idx >= waypoints.length) {
      isAnimatingRef.current = false;
      onCompleteRef.current?.();
      return;
    }

    const target = waypoints[idx];
    const pos = positionRef.current;
    const dist = pos.distanceTo(target);

    if (dist < ARRIVAL_THRESHOLD) {
      // Snap precisely to waypoint before advancing
      pos.copy(target);
      waypointIndexRef.current++;

      if (waypointIndexRef.current >= waypoints.length) {
        isAnimatingRef.current = false;
        onCompleteRef.current?.();
      }
    } else {
      // Lerp step proportional to elapsed time and travel speed
      const stepFraction = Math.min((ANIMATION_SPEED * delta) / dist, 1);
      pos.lerp(target, stepFraction);
    }
  });

  return { positionRef, isAnimatingRef, animateTo, snapTo };
}
