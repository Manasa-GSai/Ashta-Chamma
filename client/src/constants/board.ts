/**
 * Board constants for Ashta Chamma.
 *
 * The board is a 9×9 grid with a cross-shaped playing area.
 * A cell (row, col) is valid when row ∈ [3..5] OR col ∈ [3..5],
 * matching the legacy game.py 9×9 internal coordinate grid.
 */

export const BOARD_SIZE = 9;

/** Rendered width and depth of each square in Three.js world units. */
export const SQUARE_SIZE = 1.0;

/** Gap between adjacent squares. */
export const SQUARE_GAP = 0.06;

/** Height (thickness) of each square mesh. */
export const SQUARE_HEIGHT = 0.15;

/** Combined step between square centres (size + gap). */
export const SQUARE_STEP = SQUARE_SIZE + SQUARE_GAP;

export type PlayerColor = 'red' | 'blue' | 'green' | 'yellow';

export type CellType =
  | 'normal'
  | 'safe'
  | 'center'
  | 'home_red'
  | 'home_blue'
  | 'home_green'
  | 'home_yellow';

export interface BoardCell {
  readonly row: number;
  readonly col: number;
}

/**
 * Returns true when (row, col) belongs to the cross-shaped board.
 * Cross is formed by the middle three rows (3-5) and middle three columns (3-5).
 */
export function isBoardCell(row: number, col: number): boolean {
  return (row >= 3 && row <= 5) || (col >= 3 && col <= 5);
}

/** Returns all 45 valid board cells. */
export function getBoardCells(): BoardCell[] {
  const cells: BoardCell[] = [];
  for (let row = 0; row < BOARD_SIZE; row++) {
    for (let col = 0; col < BOARD_SIZE; col++) {
      if (isBoardCell(row, col)) {
        cells.push({ row, col });
      }
    }
  }
  return cells;
}

/** Center (winning) position — (4,4) is the final home square. */
export const CENTER_CELL: BoardCell = { row: 4, col: 4 };

/**
 * Nine safe squares where pawns cannot be captured.
 * Positioned symmetrically along the centre row and column,
 * matching the traditional Ashta Chamma safe-square layout.
 */
export const SAFE_SQUARES: ReadonlyArray<BoardCell> = [
  { row: 0, col: 4 },
  { row: 2, col: 4 },
  { row: 4, col: 0 },
  { row: 4, col: 2 },
  { row: 4, col: 4 }, // center — also the winning position
  { row: 4, col: 6 },
  { row: 4, col: 8 },
  { row: 6, col: 4 },
  { row: 8, col: 4 },
];

/**
 * Returns true when (row, col) is a safe square.
 * Uses a fast Set-based lookup built from SAFE_SQUARES.
 */
const _safeSquareKeys = new Set<string>(
  SAFE_SQUARES.map(({ row, col }) => `${row},${col}`),
);
export function isSafeSquare(row: number, col: number): boolean {
  return _safeSquareKeys.has(`${row},${col}`);
}

/**
 * Home zones — the three-column arms at each end of the cross.
 * Each arm (9 cells) is assigned to a player colour.
 * Top arm → Red, Right arm → Blue, Bottom arm → Green, Left arm → Yellow.
 */
export const HOME_ZONES: ReadonlyArray<{
  player: PlayerColor;
  cells: ReadonlyArray<BoardCell>;
}> = [
  {
    player: 'red',
    cells: (() => {
      const result: BoardCell[] = [];
      for (let r = 0; r <= 2; r++) {
        for (let c = 3; c <= 5; c++) {
          result.push({ row: r, col: c });
        }
      }
      return result;
    })(),
  },
  {
    player: 'blue',
    cells: (() => {
      const result: BoardCell[] = [];
      for (let r = 3; r <= 5; r++) {
        for (let c = 6; c <= 8; c++) {
          result.push({ row: r, col: c });
        }
      }
      return result;
    })(),
  },
  {
    player: 'green',
    cells: (() => {
      const result: BoardCell[] = [];
      for (let r = 6; r <= 8; r++) {
        for (let c = 3; c <= 5; c++) {
          result.push({ row: r, col: c });
        }
      }
      return result;
    })(),
  },
  {
    player: 'yellow',
    cells: (() => {
      const result: BoardCell[] = [];
      for (let r = 3; r <= 5; r++) {
        for (let c = 0; c <= 2; c++) {
          result.push({ row: r, col: c });
        }
      }
      return result;
    })(),
  },
];

const _homeZoneMap = new Map<string, PlayerColor>();
for (const zone of HOME_ZONES) {
  for (const { row, col } of zone.cells) {
    _homeZoneMap.set(`${row},${col}`, zone.player);
  }
}

/**
 * Derives the visual cell type for a board coordinate.
 * Priority: center > safe > home zone > normal.
 */
export function getCellType(row: number, col: number): CellType {
  if (row === CENTER_CELL.row && col === CENTER_CELL.col) {
    return 'center';
  }
  if (isSafeSquare(row, col)) {
    return 'safe';
  }
  const homePlayer = _homeZoneMap.get(`${row},${col}`);
  if (homePlayer !== undefined) {
    return `home_${homePlayer}` as CellType;
  }
  return 'normal';
}

/**
 * Converts a (row, col) board coordinate to a Three.js world position.
 * The board is centred at the origin; x maps to column, z maps to row.
 * Returns [x, y, z] where y = 0 (top face of the square).
 */
export function cellTo3D(row: number, col: number): [number, number, number] {
  const offset = ((BOARD_SIZE - 1) / 2) * SQUARE_STEP;
  return [col * SQUARE_STEP - offset, 0, row * SQUARE_STEP - offset];
}
