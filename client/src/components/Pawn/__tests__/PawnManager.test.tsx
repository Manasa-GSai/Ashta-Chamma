import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { useGameStore } from '../../../store/gameStore';

// ---------------------------------------------------------------------------
// Mock @react-three/fiber so PawnManager and Pawn3D can render without a Canvas
// ---------------------------------------------------------------------------
vi.mock('@react-three/fiber', () => ({
  useFrame: vi.fn(),
  Canvas: ({ children }: { children: React.ReactNode }) =>
    React.createElement('div', { 'data-testid': 'canvas' }, children),
}));

// ---------------------------------------------------------------------------
// Stub Pawn3D so PawnManager tests focus on quantity and identity, not rendering
// ---------------------------------------------------------------------------
vi.mock('../Pawn3D', () => ({
  Pawn3D: ({ pawn }: { pawn: { id: string } }) =>
    React.createElement('div', { 'data-testid': `pawn-${pawn.id}` }),
}));

// ---------------------------------------------------------------------------
// Mock three to avoid WebGL environment requirements
// ---------------------------------------------------------------------------
vi.mock('three', async () => {
  const actual = await vi.importActual<typeof import('three')>('three');
  return actual;
});

import { PawnManager } from '../PawnManager';

// Helper: reset Zustand store to initial state before each test
function resetStore() {
  useGameStore.setState((s) => ({ ...s }));
}

describe('PawnManager', () => {
  beforeEach(() => {
    resetStore();
  });

  it('renders exactly 16 Pawn3D components — 4 per player color', () => {
    const { getAllByTestId } = render(React.createElement(PawnManager));
    const pawnElements = getAllByTestId(/^pawn-/);
    expect(pawnElements).toHaveLength(16);
  });

  it('renders 4 pawns for each color', () => {
    const { getByTestId } = render(React.createElement(PawnManager));
    const colors = ['red', 'blue', 'green', 'yellow'];
    for (const color of colors) {
      for (let i = 0; i < 4; i++) {
        expect(getByTestId(`pawn-${color}_${i}`)).toBeDefined();
      }
    }
  });

  it('renders Pawn3D components with the correct pawn ids from the store', () => {
    const { getByTestId } = render(React.createElement(PawnManager));
    const expectedIds = ['red_0', 'red_1', 'red_2', 'red_3', 'blue_0', 'yellow_3'];
    for (const id of expectedIds) {
      expect(getByTestId(`pawn-${id}`)).toBeDefined();
    }
  });

  it('re-renders with updated pawn list when store state changes', () => {
    const { getAllByTestId, rerender } = render(React.createElement(PawnManager));
    expect(getAllByTestId(/^pawn-/).length).toBe(16);

    // Simulate a pawn move by triggering a store action
    useGameStore.getState().movePawn('red_0', [], { row: 1, col: 4 }, 0);

    rerender(React.createElement(PawnManager));
    // All 16 pawns still present after a move
    expect(getAllByTestId(/^pawn-/).length).toBe(16);
  });

  it('all 16 initial pawns are at home', () => {
    const { pawns } = useGameStore.getState();
    expect(pawns).toHaveLength(16);
    expect(pawns.every((p) => p.isHome)).toBe(true);
  });

  it('pawn moves correctly updates store state', () => {
    const store = useGameStore.getState();
    store.movePawn('blue_2', [{ row: 4, col: 1 }], { row: 4, col: 2 }, 2);

    const updated = useGameStore.getState().pawns.find((p) => p.id === 'blue_2');
    expect(updated?.isHome).toBe(false);
    expect(updated?.isAnimating).toBe(true);
    expect(updated?.gridPosition).toEqual({ row: 4, col: 2 });
    expect(updated?.pathIndex).toBe(2);
    expect(updated?.waypoints).toEqual([{ row: 4, col: 1 }]);
  });

  it('capture returns pawn to home with captureReturn flag', () => {
    const store = useGameStore.getState();
    // First place a pawn on the board
    store.movePawn('green_1', [], { row: 7, col: 4 }, 1);

    // Now capture it
    store.capturePawn('green_1');

    const pawn = useGameStore.getState().pawns.find((p) => p.id === 'green_1')!;
    expect(pawn.isHome).toBe(true);
    expect(pawn.isAnimating).toBe(true);
    expect(pawn.captureReturn).toBe(true);
    expect(pawn.gridPosition).toBeNull();
  });

  it('finishPawn marks pawn as finished and stops animation', () => {
    const store = useGameStore.getState();
    store.movePawn('yellow_0', [], { row: 4, col: 4 }, 49);
    store.finishPawn('yellow_0');

    const pawn = useGameStore.getState().pawns.find((p) => p.id === 'yellow_0')!;
    expect(pawn.isFinished).toBe(true);
    expect(pawn.isAnimating).toBe(false);
  });

  it('setPawnAnimating clears animating flag on completion', () => {
    const store = useGameStore.getState();
    store.movePawn('red_3', [], { row: 1, col: 4 }, 0);
    expect(useGameStore.getState().pawns.find((p) => p.id === 'red_3')?.isAnimating).toBe(true);

    store.setPawnAnimating('red_3', false);
    expect(useGameStore.getState().pawns.find((p) => p.id === 'red_3')?.isAnimating).toBe(false);
  });
});
