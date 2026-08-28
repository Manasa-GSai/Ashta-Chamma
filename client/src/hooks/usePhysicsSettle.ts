import { useCallback, useEffect, useRef } from 'react';
import type { RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import type { RapierRigidBody } from '@react-three/rapier';

/**
 * Velocity thresholds below which a rigid body is considered "at rest".
 * Tuned for small cowrie shells (mass ~0.08kg) on a flat surface.
 */
const LINEAR_VELOCITY_THRESHOLD = 0.05; // m/s
const ANGULAR_VELOCITY_THRESHOLD = 0.05; // rad/s

/**
 * Number of consecutive frames all bodies must be below threshold
 * before settle is declared (avoids false positives from momentary pauses).
 */
const REQUIRED_SETTLED_FRAMES = 20;

/**
 * Maximum time (ms) allowed before settle is force-triggered.
 * Ensures the animation never hangs even on unusual physics outcomes.
 */
const SETTLE_TIMEOUT_MS = 2000;

export interface UsePhysicsSettleOptions {
  /** Refs to the rigid bodies that should all settle before firing onSettled. */
  rigidBodyRefs: Array<RefObject<RapierRigidBody | null>>;
  /**
   * When true, begin monitoring for settle condition and start the timeout.
   * Resetting to false then back to true restarts the monitoring cycle.
   */
  isActive: boolean;
  /** Fired exactly once per active cycle, either from velocity check or timeout. */
  onSettled: () => void;
}

export interface UsePhysicsSettleResult {
  /** Immediately fire onSettled, bypassing velocity checks (e.g. user abort). */
  forceSettle: () => void;
}

/**
 * Monitors Rapier rigid bodies each frame and fires `onSettled` once all
 * bodies have been below velocity thresholds for `REQUIRED_SETTLED_FRAMES`
 * consecutive frames — or after `SETTLE_TIMEOUT_MS`, whichever comes first.
 *
 * Must be called inside a component that is rendered within <Canvas> and <Physics>.
 */
export const usePhysicsSettle = ({
  rigidBodyRefs,
  isActive,
  onSettled,
}: UsePhysicsSettleOptions): UsePhysicsSettleResult => {
  const settledFrameCount = useRef(0);
  const hasCalledSettled = useRef(false);
  const timeoutIdRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const triggerSettled = useCallback(() => {
    if (hasCalledSettled.current) return;
    hasCalledSettled.current = true;
    if (timeoutIdRef.current !== null) {
      clearTimeout(timeoutIdRef.current);
      timeoutIdRef.current = null;
    }
    onSettled();
  }, [onSettled]);

  // Start / restart the monitoring cycle whenever isActive toggles on.
  useEffect(() => {
    if (!isActive) return;

    settledFrameCount.current = 0;
    hasCalledSettled.current = false;

    // Force-settle after the maximum allowed duration.
    timeoutIdRef.current = setTimeout(triggerSettled, SETTLE_TIMEOUT_MS);

    return () => {
      if (timeoutIdRef.current !== null) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }
    };
  }, [isActive, triggerSettled]);

  // Per-frame velocity check — runs every render frame while inside Canvas.
  useFrame(() => {
    if (!isActive || hasCalledSettled.current) return;

    const allBelowThreshold = rigidBodyRefs.every((bodyRef) => {
      const body = bodyRef.current;
      if (body === null || body === undefined) return true;

      const { x: lx, y: ly, z: lz } = body.linvel();
      const { x: ax, y: ay, z: az } = body.angvel();

      const linearSpeed = Math.sqrt(lx * lx + ly * ly + lz * lz);
      const angularSpeed = Math.sqrt(ax * ax + ay * ay + az * az);

      return linearSpeed < LINEAR_VELOCITY_THRESHOLD && angularSpeed < ANGULAR_VELOCITY_THRESHOLD;
    });

    if (allBelowThreshold) {
      settledFrameCount.current += 1;
    } else {
      settledFrameCount.current = 0;
    }

    if (settledFrameCount.current >= REQUIRED_SETTLED_FRAMES) {
      triggerSettled();
    }
  });

  return { forceSettle: triggerSettled };
};
