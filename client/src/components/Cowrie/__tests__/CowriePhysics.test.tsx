/**
 * Tests for CowriePhysics component and the usePhysicsSettle hook.
 *
 * Heavy 3D/physics dependencies are mocked so tests run in jsdom without
 * WebGL or WASM — only the React component lifecycle and timing logic is
 * exercised here.
 */
import React from 'react';
import { render, act } from '@testing-library/react';
import { renderHook } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// ---------------------------------------------------------------------------
// Mock @react-three/fiber — no WebGL canvas required
// ---------------------------------------------------------------------------

const frameCallbacks: Array<(state: unknown, delta: number) => void> = [];

vi.mock('@react-three/fiber', () => ({
  useFrame: (cb: (state: unknown, delta: number) => void) => {
    frameCallbacks.push(cb);
  },
  Canvas: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="r3f-canvas">{children}</div>
  ),
}));

// ---------------------------------------------------------------------------
// Mock @react-three/rapier — no WASM required
// ---------------------------------------------------------------------------

const mockRigidBody = {
  linvel: () => ({ x: 0, y: 0, z: 0 }),
  angvel: () => ({ x: 0, y: 0, z: 0 }),
  setTranslation: vi.fn(),
  setRotation: vi.fn(),
  setLinvel: vi.fn(),
  setAngvel: vi.fn(),
  setBodyType: vi.fn(),
  setNextKinematicRotation: vi.fn(),
  rotation: () => ({ x: 0, y: 0, z: 0, w: 1 }),
  wakeUp: vi.fn(),
  applyImpulse: vi.fn(),
  applyTorqueImpulse: vi.fn(),
};

vi.mock('@react-three/rapier', () => ({
  Physics: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  RigidBody: React.forwardRef(
    (
      { children }: { children?: React.ReactNode },
      _ref: React.Ref<unknown>,
    ) => <group>{children}</group>,
  ),
  BallCollider: () => null,
  CuboidCollider: () => null,
  useRapier: () => ({
    rapier: {
      RigidBodyType: {
        Dynamic: 0,
        Fixed: 1,
        KinematicPositionBased: 2,
        KinematicVelocityBased: 3,
      },
    },
  }),
}));

// ---------------------------------------------------------------------------
// Mock three — keep real math classes, just prevent WebGL side-effects
// ---------------------------------------------------------------------------

vi.mock('three', async () => {
  const actual = await vi.importActual<typeof import('three')>('three');
  return actual;
});

// ---------------------------------------------------------------------------
// Mock CowrieShell — pure geometry, not what we are testing here
// ---------------------------------------------------------------------------

vi.mock('../CowrieShell', () => ({
  CowrieShell: () => <mesh data-testid="cowrie-shell-mesh" />,
}));

// ---------------------------------------------------------------------------
// Import the actual modules under test AFTER mocks are set up
// ---------------------------------------------------------------------------

import { CowriePhysics } from '../CowriePhysics';
import { usePhysicsSettle } from '../../../hooks/usePhysicsSettle';
import type { UsePhysicsSettleOptions } from '../../../hooks/usePhysicsSettle';

// ---------------------------------------------------------------------------
// Helper: flush all registered useFrame callbacks
// ---------------------------------------------------------------------------
function flushFrames(count: number = 1, delta: number = 0.016): void {
  for (let f = 0; f < count; f++) {
    frameCallbacks.forEach((cb) => cb({}, delta));
  }
}

// ---------------------------------------------------------------------------
// CowriePhysics component tests
// ---------------------------------------------------------------------------

describe('CowriePhysics', () => {
  beforeEach(() => {
    frameCallbacks.length = 0;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('mounts without throwing errors', () => {
    const onSettled = vi.fn();
    expect(() => {
      render(
        <CowriePhysics
          rollResult={null}
          rollTrigger={0}
          onSettled={onSettled}
        />,
      );
    }).not.toThrow();
  });

  it('renders without calling onSettled when idle', () => {
    const onSettled = vi.fn();
    render(
      <CowriePhysics
        rollResult={null}
        rollTrigger={0}
        onSettled={onSettled}
      />,
    );
    flushFrames(60); // simulate 1 second of frames
    expect(onSettled).not.toHaveBeenCalled();
  });

  it('accepts a 4-element boolean rollResult without errors', () => {
    const onSettled = vi.fn();
    expect(() => {
      render(
        <CowriePhysics
          rollResult={[true, false, true, false]}
          rollTrigger={1}
          onSettled={onSettled}
        />,
      );
    }).not.toThrow();
  });

  it('calls onSettled within 3 seconds via settle timeout', async () => {
    const onSettled = vi.fn();

    render(
      <CowriePhysics
        rollResult={[true, false, true, false]}
        rollTrigger={1}
        onSettled={onSettled}
      />,
    );

    // The usePhysicsSettle timeout fires after 2 s — advance past it.
    // Wrapped in act so React can process state updates from setTimeout.
    await act(async () => {
      vi.advanceTimersByTime(2500);
    });

    // After physics settles (via timeout), the lerp phase begins.
    // Run enough frames at delta=0.016 (~60 FPS) to complete the 1-second lerp.
    // LERP_SPEED=4.0 means ~100% progress after 0.25 s → 16 frames is enough.
    act(() => {
      flushFrames(60, 0.016);
    });

    // onSettled should have been called by now.
    expect(onSettled).toHaveBeenCalledOnce();
  });
});

// ---------------------------------------------------------------------------
// usePhysicsSettle hook tests
// ---------------------------------------------------------------------------

describe('usePhysicsSettle', () => {
  beforeEach(() => {
    frameCallbacks.length = 0;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  function makeOptions(
    overrides: Partial<UsePhysicsSettleOptions> = {},
  ): UsePhysicsSettleOptions {
    return {
      rigidBodyRefs: [],
      isActive: false,
      onSettled: vi.fn(),
      ...overrides,
    };
  }

  it('does not call onSettled when isActive is false', () => {
    const onSettled = vi.fn();
    renderHook(() => usePhysicsSettle(makeOptions({ isActive: false, onSettled })));

    flushFrames(120);
    act(() => { vi.advanceTimersByTime(3000); });

    expect(onSettled).not.toHaveBeenCalled();
  });

  it('calls onSettled via timeout when isActive becomes true', () => {
    const onSettled = vi.fn();
    renderHook(() => usePhysicsSettle(makeOptions({ isActive: true, onSettled })));

    act(() => { vi.advanceTimersByTime(2100); });

    expect(onSettled).toHaveBeenCalledOnce();
  });

  it('calls onSettled only once even when timeout and frame both try to fire', () => {
    const onSettled = vi.fn();

    // Simulate a body that is already at rest (zero velocity) — will reach
    // REQUIRED_SETTLED_FRAMES quickly AND the timeout fires.
    const mockBodyRef = {
      current: {
        ...mockRigidBody,
        linvel: () => ({ x: 0, y: 0, z: 0 }),
        angvel: () => ({ x: 0, y: 0, z: 0 }),
      },
    } as unknown as React.RefObject<import('@react-three/rapier').RapierRigidBody | null>;

    renderHook(() =>
      usePhysicsSettle(
        makeOptions({ isActive: true, onSettled, rigidBodyRefs: [mockBodyRef] }),
      ),
    );

    // Run 30 frames — body is already still so threshold is met immediately.
    flushFrames(30);

    // Also advance past the timeout to confirm double-fire is prevented.
    act(() => { vi.advanceTimersByTime(3000); });

    expect(onSettled).toHaveBeenCalledOnce();
  });

  it('forceSettle immediately triggers onSettled', () => {
    const onSettled = vi.fn();
    const { result } = renderHook(() =>
      usePhysicsSettle(makeOptions({ isActive: true, onSettled })),
    );

    result.current.forceSettle();

    expect(onSettled).toHaveBeenCalledOnce();
  });

  it('resets and fires again when isActive cycles off and on', () => {
    const onSettled = vi.fn();
    const { rerender } = renderHook(
      ({ active }: { active: boolean }) =>
        usePhysicsSettle(makeOptions({ isActive: active, onSettled })),
      { initialProps: { active: true } },
    );

    // First cycle — timeout fires.
    act(() => { vi.advanceTimersByTime(2100); });
    expect(onSettled).toHaveBeenCalledTimes(1);

    // Deactivate then reactivate to start a new cycle.
    rerender({ active: false });
    rerender({ active: true });

    act(() => { vi.advanceTimersByTime(2100); });
    expect(onSettled).toHaveBeenCalledTimes(2);
  });
});
