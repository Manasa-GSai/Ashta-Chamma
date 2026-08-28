import { Vector3 } from 'three';

/** Size of each board cell in world units. Board is 9×9 cells (indices 0–8). */
export const CELL_SIZE = 1.0;

/** Y offset for pawns sitting just above the board surface */
export const PAWN_Y_OFFSET = 0.05;

/**
 * Converts a 9×9 grid position to a Three.js world coordinate.
 * Center cell (row=4, col=4) maps to world origin (0, 0, 0).
 */
export function gridToWorld(row: number, col: number): Vector3 {
  const x = (col - 4) * CELL_SIZE;
  const z = (row - 4) * CELL_SIZE;
  return new Vector3(x, PAWN_Y_OFFSET, z);
}

export type PlayerColor = 'red' | 'blue' | 'green' | 'yellow';

/**
 * Maps player colors to their numeric index.
 * Matches the legacy player.py Player class color ordering.
 */
export const COLOR_INDEX: Record<PlayerColor, number> = {
  red: 0,
  blue: 1,
  green: 2,
  yellow: 3,
};

/**
 * Home base center grid positions for each player.
 * Derived from player.py: cells[i*4][((i+1)%2)*4] for i∈{0,1,2}, and cells[4][8] for i=3.
 */
export const HOME_GRID: Record<PlayerColor, { row: number; col: number }> = {
  red: { row: 0, col: 4 },
  blue: { row: 4, col: 0 },
  green: { row: 8, col: 4 },
  yellow: { row: 4, col: 8 },
};

/**
 * Offsets (in cell fractions) for grouping 4 pawns within their home base.
 * Pawns are arranged in a 2×2 formation.
 */
const HOME_PAWN_OFFSETS: ReadonlyArray<{ dr: number; dc: number }> = [
  { dr: -0.28, dc: -0.28 },
  { dr: -0.28, dc: 0.28 },
  { dr: 0.28, dc: -0.28 },
  { dr: 0.28, dc: 0.28 },
];

/**
 * Returns the world position for a pawn waiting at its home base.
 * All 4 pawns of a color are grouped in a 2×2 cluster near their home cell.
 */
export function homePosition(color: PlayerColor, pawnIndex: number): Vector3 {
  const base = HOME_GRID[color];
  const offset = HOME_PAWN_OFFSETS[pawnIndex % 4];
  const x = (base.col + offset.dc - 4) * CELL_SIZE;
  const z = (base.row + offset.dr - 4) * CELL_SIZE;
  return new Vector3(x, PAWN_Y_OFFSET, z);
}

/**
 * Slight offsets within the center square for finished pawns of each color.
 * Keeps all 4 colors visible after reaching (4,4).
 */
const CENTER_OFFSETS: Record<PlayerColor, { dx: number; dz: number }> = {
  red: { dx: -0.18, dz: -0.18 },
  blue: { dx: -0.18, dz: 0.18 },
  green: { dx: 0.18, dz: 0.18 },
  yellow: { dx: 0.18, dz: -0.18 },
};

/**
 * Returns the world position for a pawn that has reached the center win square (4,4).
 * Each color is offset slightly so all finished pawns are distinguishable.
 */
export function centerPosition(color: PlayerColor): Vector3 {
  const off = CENTER_OFFSETS[color];
  // Raise finished pawns slightly above the surface for visual distinction
  return new Vector3(off.dx, PAWN_Y_OFFSET + 0.12, off.dz);
}

/**
 * Generates a series of arc waypoints (as world Vector3s) for a capture-return animation.
 * The arc rises to `arcHeight` world units at its midpoint, creating a parabolic trajectory.
 */
export function generateCaptureArc(
  fromWorld: Vector3,
  toWorld: Vector3,
  arcHeight: number = 1.8,
): Vector3[] {
  const mid = new Vector3().lerpVectors(fromWorld, toWorld, 0.5);
  mid.y += arcHeight;

  // Four intermediate points to approximate a smooth parabola
  const q1 = new Vector3().lerpVectors(fromWorld, mid, 0.4);
  q1.y = fromWorld.y + arcHeight * 0.6;

  const q2 = new Vector3().lerpVectors(mid, toWorld, 0.4);
  q2.y = toWorld.y + arcHeight * 0.6;

  return [q1, mid, q2, toWorld.clone()];
}

/**
 * Board paths for each player color.
 * Ported directly from path.py: each array contains (row, col) tuples
 * describing the full movement track from start (index 0) to center (index 48).
 */
export const BOARD_PATHS: Record<PlayerColor, ReadonlyArray<readonly [number, number]>> = {
  red: [
    [0, 4], [1, 4], [1, 3], [1, 2], [1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1],
    [7, 1], [7, 2], [7, 3], [7, 4], [7, 5], [7, 6], [7, 7], [6, 7], [5, 7], [4, 7],
    [3, 7], [2, 7], [1, 7], [1, 6], [1, 5], [2, 6], [3, 6], [4, 6], [5, 6], [6, 6],
    [6, 5], [6, 4], [6, 3], [6, 2], [5, 2], [4, 2], [3, 2], [2, 2], [2, 3], [2, 4],
    [2, 5], [3, 5], [4, 5], [5, 5], [5, 4], [5, 3], [4, 3], [3, 3], [3, 4], [4, 4],
  ],
  blue: [
    [4, 0], [4, 1], [5, 1], [6, 1], [7, 1], [7, 2], [7, 3], [7, 4], [7, 5], [7, 6],
    [7, 7], [6, 7], [5, 7], [4, 7], [3, 7], [2, 7], [1, 7], [1, 6], [1, 5], [1, 4],
    [1, 3], [1, 2], [1, 1], [2, 1], [3, 1], [2, 2], [2, 3], [2, 4], [2, 5], [2, 6],
    [3, 6], [4, 6], [5, 6], [6, 6], [6, 5], [6, 4], [6, 3], [6, 2], [5, 2], [4, 2],
    [3, 2], [3, 3], [3, 4], [3, 5], [4, 5], [5, 5], [5, 4], [5, 3], [4, 3], [4, 4],
  ],
  green: [
    [8, 4], [7, 4], [7, 5], [7, 6], [7, 7], [6, 7], [5, 7], [4, 7], [3, 7], [2, 7],
    [1, 7], [1, 6], [1, 5], [1, 4], [1, 3], [1, 2], [1, 1], [2, 1], [3, 1], [4, 1],
    [5, 1], [6, 1], [7, 1], [7, 2], [7, 3], [6, 2], [5, 2], [4, 2], [3, 2], [2, 2],
    [2, 3], [2, 4], [2, 5], [2, 6], [3, 6], [4, 6], [5, 6], [6, 6], [6, 5], [6, 4],
    [6, 3], [5, 3], [4, 3], [3, 3], [3, 4], [3, 5], [4, 5], [5, 5], [5, 4], [4, 4],
  ],
  yellow: [
    [4, 8], [4, 7], [3, 7], [2, 7], [1, 7], [1, 6], [1, 5], [1, 4], [1, 3], [1, 2],
    [1, 1], [2, 1], [3, 1], [4, 1], [5, 1], [6, 1], [7, 1], [7, 2], [7, 3], [7, 4],
    [7, 5], [7, 6], [7, 7], [6, 7], [5, 7], [6, 6], [6, 5], [6, 4], [6, 3], [6, 2],
    [5, 2], [4, 2], [3, 2], [2, 2], [2, 3], [2, 4], [2, 5], [2, 6], [3, 6], [4, 6],
    [5, 6], [5, 5], [5, 4], [5, 3], [4, 3], [3, 3], [3, 4], [3, 5], [4, 5], [4, 4],
  ],
};

/** Index of the center/finish square in every player's path (0-indexed). */
export const FINISH_PATH_INDEX = 49;
