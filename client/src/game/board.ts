import type { Position } from "./types";

export const BOARD_SIZE = 5;

export const SAFE_POSITIONS: Position[] = [
  { row: 0, col: 0 },
  { row: 0, col: 2 },
  { row: 0, col: 4 },
  { row: 2, col: 0 },
  { row: 2, col: 4 },
  { row: 4, col: 0 },
  { row: 4, col: 2 },
  { row: 4, col: 4 },
];

export const CENTER: Position = { row: 2, col: 2 };

export function isSafe(pos: Position): boolean {
  return SAFE_POSITIONS.some((s) => s.row === pos.row && s.col === pos.col);
}

export function isCenter(pos: Position): boolean {
  return pos.row === CENTER.row && pos.col === CENTER.col;
}

export function posKey(pos: Position): string {
  return `${pos.row},${pos.col}`;
}

const OUTER_RING: Position[] = [
  { row: 4, col: 2 },
  { row: 4, col: 1 },
  { row: 4, col: 0 },
  { row: 3, col: 0 },
  { row: 2, col: 0 },
  { row: 1, col: 0 },
  { row: 0, col: 0 },
  { row: 0, col: 1 },
  { row: 0, col: 2 },
  { row: 0, col: 3 },
  { row: 0, col: 4 },
  { row: 1, col: 4 },
  { row: 2, col: 4 },
  { row: 3, col: 4 },
  { row: 4, col: 4 },
  { row: 4, col: 3 },
];

const INNER_RINGS: Position[][] = [
  [
    { row: 3, col: 3 }, { row: 3, col: 2 }, { row: 3, col: 1 },
    { row: 2, col: 1 }, { row: 1, col: 1 }, { row: 1, col: 2 },
    { row: 1, col: 3 }, { row: 2, col: 3 },
  ],
  [
    { row: 3, col: 1 }, { row: 2, col: 1 }, { row: 1, col: 1 },
    { row: 1, col: 2 }, { row: 1, col: 3 }, { row: 2, col: 3 },
    { row: 3, col: 3 }, { row: 3, col: 2 },
  ],
  [
    { row: 1, col: 1 }, { row: 1, col: 2 }, { row: 1, col: 3 },
    { row: 2, col: 3 }, { row: 3, col: 3 }, { row: 3, col: 2 },
    { row: 3, col: 1 }, { row: 2, col: 1 },
  ],
  [
    { row: 1, col: 3 }, { row: 2, col: 3 }, { row: 3, col: 3 },
    { row: 3, col: 2 }, { row: 3, col: 1 }, { row: 2, col: 1 },
    { row: 1, col: 1 }, { row: 1, col: 2 },
  ],
];

function buildPath(playerIndex: number): Position[] {
  const outerStart = playerIndex * 4;
  const outer: Position[] = [];
  for (let i = 0; i < 16; i++) {
    outer.push(OUTER_RING[(outerStart + i) % 16]);
  }
  return [...outer, ...INNER_RINGS[playerIndex], CENTER];
}

export const PATHS: Position[][] = [
  buildPath(0),
  buildPath(1),
  buildPath(2),
  buildPath(3),
];

export const PATH_LENGTH = 24;

export function pathToPosition(
  playerIndex: number,
  pathIndex: number,
): Position | null {
  if (pathIndex < 0 || pathIndex > PATH_LENGTH) return null;
  return PATHS[playerIndex][pathIndex];
}
