import { describe, it, expect } from 'vitest';
import {
  gridToWorld,
  homePosition,
  centerPosition,
  generateCaptureArc,
  CELL_SIZE,
  PAWN_Y_OFFSET,
  HOME_GRID,
  BOARD_PATHS,
  FINISH_PATH_INDEX,
} from '../gridToWorld';
import { Vector3 } from 'three';

describe('gridToWorld', () => {
  it('maps center cell (4,4) to world origin with PAWN_Y_OFFSET', () => {
    const pos = gridToWorld(4, 4);
    expect(pos.x).toBeCloseTo(0);
    expect(pos.y).toBe(PAWN_Y_OFFSET);
    expect(pos.z).toBeCloseTo(0);
  });

  it('maps top-center cell (0,4) correctly', () => {
    const pos = gridToWorld(0, 4);
    expect(pos.x).toBeCloseTo(0);
    expect(pos.y).toBe(PAWN_Y_OFFSET);
    expect(pos.z).toBeCloseTo(-4 * CELL_SIZE);
  });

  it('maps bottom-right cell (8,8) correctly', () => {
    const pos = gridToWorld(8, 8);
    expect(pos.x).toBeCloseTo(4 * CELL_SIZE);
    expect(pos.z).toBeCloseTo(4 * CELL_SIZE);
  });

  it('maps left-center cell (4,0) correctly', () => {
    const pos = gridToWorld(4, 0);
    expect(pos.x).toBeCloseTo(-4 * CELL_SIZE);
    expect(pos.z).toBeCloseTo(0);
  });

  it('returns a new Vector3 instance each call', () => {
    const a = gridToWorld(1, 1);
    const b = gridToWorld(1, 1);
    expect(a).not.toBe(b);
    expect(a.equals(b)).toBe(true);
  });
});

describe('homePosition', () => {
  it('places red pawns near the top-center (0,4)', () => {
    const base = HOME_GRID.red;
    for (let i = 0; i < 4; i++) {
      const pos = homePosition('red', i);
      // All 4 red pawns must be within 1 cell of the home grid center
      expect(Math.abs(pos.x - (base.col - 4) * CELL_SIZE)).toBeLessThan(CELL_SIZE);
      expect(Math.abs(pos.z - (base.row - 4) * CELL_SIZE)).toBeLessThan(CELL_SIZE);
    }
  });

  it('places all 4 pawns at distinct positions', () => {
    const positions = [0, 1, 2, 3].map((i) => homePosition('blue', i));
    const keys = positions.map((p) => `${p.x.toFixed(4)},${p.z.toFixed(4)}`);
    expect(new Set(keys).size).toBe(4);
  });

  it('places green pawns near the bottom-center (8,4)', () => {
    const base = HOME_GRID.green;
    const pos = homePosition('green', 0);
    expect(Math.abs(pos.z - (base.row - 4) * CELL_SIZE)).toBeLessThan(CELL_SIZE);
  });

  it('places yellow pawns near the right-center (4,8)', () => {
    const base = HOME_GRID.yellow;
    const pos = homePosition('yellow', 0);
    expect(Math.abs(pos.x - (base.col - 4) * CELL_SIZE)).toBeLessThan(CELL_SIZE);
  });

  it('y coordinate equals PAWN_Y_OFFSET', () => {
    expect(homePosition('red', 0).y).toBe(PAWN_Y_OFFSET);
  });
});

describe('centerPosition', () => {
  it('places all colors near the world origin', () => {
    const colors = ['red', 'blue', 'green', 'yellow'] as const;
    for (const color of colors) {
      const pos = centerPosition(color);
      expect(Math.abs(pos.x)).toBeLessThan(0.5);
      expect(Math.abs(pos.z)).toBeLessThan(0.5);
    }
  });

  it('places each color at a distinct position', () => {
    const keys = (['red', 'blue', 'green', 'yellow'] as const).map((c) => {
      const p = centerPosition(c);
      return `${p.x.toFixed(4)},${p.z.toFixed(4)}`;
    });
    expect(new Set(keys).size).toBe(4);
  });

  it('raises finished pawns above PAWN_Y_OFFSET', () => {
    expect(centerPosition('red').y).toBeGreaterThan(PAWN_Y_OFFSET);
  });
});

describe('generateCaptureArc', () => {
  it('last waypoint equals the destination', () => {
    const from = new Vector3(0, PAWN_Y_OFFSET, -4);
    const to = new Vector3(-4, PAWN_Y_OFFSET, 0);
    const arc = generateCaptureArc(from, to);
    const last = arc[arc.length - 1];
    expect(last.x).toBeCloseTo(to.x);
    expect(last.y).toBeCloseTo(to.y);
    expect(last.z).toBeCloseTo(to.z);
  });

  it('arc peak is higher than start and end y', () => {
    const from = new Vector3(2, PAWN_Y_OFFSET, 0);
    const to = new Vector3(-2, PAWN_Y_OFFSET, 0);
    const arc = generateCaptureArc(from, to);
    const maxY = Math.max(...arc.map((v) => v.y));
    expect(maxY).toBeGreaterThan(PAWN_Y_OFFSET + 1);
  });

  it('returns at least 3 waypoints', () => {
    const from = new Vector3(0, 0, 0);
    const to = new Vector3(3, 0, 3);
    expect(generateCaptureArc(from, to).length).toBeGreaterThanOrEqual(3);
  });
});

describe('BOARD_PATHS', () => {
  const colors = ['red', 'blue', 'green', 'yellow'] as const;

  it.each(colors)('%s path has 50 squares (index 0..49)', (color) => {
    expect(BOARD_PATHS[color].length).toBe(FINISH_PATH_INDEX + 1);
  });

  it.each(colors)('%s path ends at center (4,4)', (color) => {
    const last = BOARD_PATHS[color][FINISH_PATH_INDEX];
    expect(last).toEqual([4, 4]);
  });

  it.each(colors)('%s path starts at its home grid position', (color) => {
    const first = BOARD_PATHS[color][0];
    const home = HOME_GRID[color];
    expect(first).toEqual([home.row, home.col]);
  });

  it('all path squares are within 9×9 grid bounds', () => {
    for (const color of colors) {
      for (const [row, col] of BOARD_PATHS[color]) {
        expect(row).toBeGreaterThanOrEqual(0);
        expect(row).toBeLessThanOrEqual(8);
        expect(col).toBeGreaterThanOrEqual(0);
        expect(col).toBeLessThanOrEqual(8);
      }
    }
  });
});
