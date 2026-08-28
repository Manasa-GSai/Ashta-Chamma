import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { Vector3 } from 'three';

// ---------------------------------------------------------------------------
// Mock useFrame so it stores the callback and lets tests invoke it manually
// ---------------------------------------------------------------------------
let frameCallback: ((state: unknown, delta: number) => void) | null = null;

vi.mock('@react-three/fiber', () => ({
  useFrame: vi.fn((cb: (state: unknown, delta: number) => void) => {
    frameCallback = cb;
  }),
}));

import { usePawnAnimation } from '../usePawnAnimation';

function runFrame(delta: number) {
  frameCallback?.({}, delta);
}

describe('usePawnAnimation', () => {
  beforeEach(() => {
    frameCallback = null;
  });

  it('initialises positionRef to the provided start position', () => {
    const start = new Vector3(1, 0.05, 2);
    const { result } = renderHook(() => usePawnAnimation(start));
    expect(result.current.positionRef.current.equals(start)).toBe(true);
  });

  it('isAnimatingRef is false initially', () => {
    const { result } = renderHook(() => usePawnAnimation(new Vector3()));
    expect(result.current.isAnimatingRef.current).toBe(false);
  });

  it('animateTo sets isAnimatingRef to true', () => {
    const { result } = renderHook(() => usePawnAnimation(new Vector3(0, 0, 0)));
    act(() => {
      result.current.animateTo([new Vector3(2, 0, 0)]);
    });
    expect(result.current.isAnimatingRef.current).toBe(true);
  });

  it('snapTo moves position immediately and clears isAnimatingRef', () => {
    const { result } = renderHook(() => usePawnAnimation(new Vector3(0, 0, 0)));
    act(() => {
      result.current.animateTo([new Vector3(5, 0, 5)]);
    });
    expect(result.current.isAnimatingRef.current).toBe(true);

    act(() => {
      result.current.snapTo(new Vector3(3, 0.05, 3));
    });
    expect(result.current.isAnimatingRef.current).toBe(false);
    expect(result.current.positionRef.current.x).toBeCloseTo(3);
    expect(result.current.positionRef.current.z).toBeCloseTo(3);
  });

  it('position moves toward waypoint each frame', () => {
    const start = new Vector3(0, 0, 0);
    const target = new Vector3(10, 0, 0);
    const { result } = renderHook(() => usePawnAnimation(start));

    act(() => {
      result.current.animateTo([target]);
    });

    const before = result.current.positionRef.current.x;
    act(() => {
      runFrame(0.016); // ~60 FPS frame
    });
    const after = result.current.positionRef.current.x;
    expect(after).toBeGreaterThan(before);
  });

  it('calls onComplete after reaching all waypoints', () => {
    const onComplete = vi.fn();
    const start = new Vector3(0, 0, 0);
    const { result } = renderHook(() =>
      usePawnAnimation(start, { onComplete }),
    );

    // Single very close waypoint — should arrive in one large delta
    act(() => {
      result.current.animateTo([new Vector3(0.001, 0, 0)]);
    });
    act(() => {
      runFrame(1.0); // Large delta — will arrive and complete
    });

    expect(onComplete).toHaveBeenCalledOnce();
    expect(result.current.isAnimatingRef.current).toBe(false);
  });

  it('ignores animateTo with empty waypoints array', () => {
    const { result } = renderHook(() => usePawnAnimation(new Vector3()));
    act(() => {
      result.current.animateTo([]);
    });
    expect(result.current.isAnimatingRef.current).toBe(false);
  });

  it('replaces an in-progress animation when animateTo is called again', () => {
    const onComplete = vi.fn();
    const { result } = renderHook(() =>
      usePawnAnimation(new Vector3(0, 0, 0), { onComplete }),
    );

    act(() => {
      result.current.animateTo([new Vector3(100, 0, 0)]); // Far away
    });
    act(() => {
      runFrame(0.016);
    });

    // Override with a close target
    act(() => {
      result.current.animateTo([new Vector3(0.001, 0, 0)]);
    });
    act(() => {
      runFrame(1.0);
    });

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it('animates through multiple waypoints in sequence', () => {
    const start = new Vector3(0, 0, 0);
    const { result } = renderHook(() => usePawnAnimation(start));

    const wp1 = new Vector3(0.001, 0, 0);
    const wp2 = new Vector3(0.001, 0, 0.001);
    act(() => {
      result.current.animateTo([wp1, wp2]);
    });

    // First frame arrives at wp1, advances to wp2
    act(() => {
      runFrame(1.0);
    });
    // Second frame arrives at wp2, completes animation
    act(() => {
      runFrame(1.0);
    });

    expect(result.current.isAnimatingRef.current).toBe(false);
  });
});
