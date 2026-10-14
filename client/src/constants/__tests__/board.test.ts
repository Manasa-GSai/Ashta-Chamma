import { describe, it, expect } from 'vitest';
import {
  BOARD_SIZE,
  SAFE_SQUARES,
  CENTER_CELL,
  isBoardCell,
  getBoardCells,
  isSafeSquare,
  getCellType,
  cellTo3D,
  HOME_ZONES,
  SQUARE_STEP,
  SQUARE_SIZE,
  SQUARE_GAP,
} from '../board';

describe('board constants', () => {
  it('BOARD_SIZE is 9', () => {
    expect(BOARD_SIZE).toBe(9);
  });

  it('SAFE_SQUARES contains exactly 9 entries', () => {
    expect(SAFE_SQUARES).toHaveLength(9);
  });

  it('CENTER_CELL is (4, 4)', () => {
    expect(CENTER_CELL).toEqual({ row: 4, col: 4 });
  });

  it('SQUARE_STEP equals SQUARE_SIZE + SQUARE_GAP', () => {
    expect(SQUARE_STEP).toBeCloseTo(SQUARE_SIZE + SQUARE_GAP);
  });
});

describe('isBoardCell', () => {
  it('returns true for cells in the middle rows (row 3-5)', () => {
    expect(isBoardCell(3, 0)).toBe(true);
    expect(isBoardCell(4, 0)).toBe(true);
    expect(isBoardCell(5, 8)).toBe(true);
  });

  it('returns true for cells in the middle columns (col 3-5)', () => {
    expect(isBoardCell(0, 3)).toBe(true);
    expect(isBoardCell(0, 4)).toBe(true);
    expect(isBoardCell(0, 5)).toBe(true);
  });

  it('returns true for the center cell', () => {
    expect(isBoardCell(4, 4)).toBe(true);
  });

  it('returns false for corner cells not on the cross', () => {
    expect(isBoardCell(0, 0)).toBe(false);
    expect(isBoardCell(0, 8)).toBe(false);
    expect(isBoardCell(8, 0)).toBe(false);
    expect(isBoardCell(8, 8)).toBe(false);
  });

  it('returns false for cells in rows 0-2 outside middle columns', () => {
    expect(isBoardCell(1, 1)).toBe(false);
    expect(isBoardCell(2, 6)).toBe(false);
  });
});

describe('getBoardCells', () => {
  const cells = getBoardCells();

  it('returns exactly 45 cells', () => {
    // Cross: 3 cols × 9 rows + 3 rows × 9 cols − 3×3 overlap = 27+27−9 = 45
    expect(cells).toHaveLength(45);
  });

  it('all returned cells are valid board cells', () => {
    for (const { row, col } of cells) {
      expect(isBoardCell(row, col)).toBe(true);
    }
  });

  it('contains the center cell', () => {
    expect(cells).toContainEqual({ row: 4, col: 4 });
  });

  it('does not contain corner cells', () => {
    expect(cells).not.toContainEqual({ row: 0, col: 0 });
    expect(cells).not.toContainEqual({ row: 8, col: 8 });
  });
});

describe('isSafeSquare', () => {
  it('returns true for all entries in SAFE_SQUARES', () => {
    for (const { row, col } of SAFE_SQUARES) {
      expect(isSafeSquare(row, col)).toBe(true);
    }
  });

  it('returns true for the center cell (4, 4)', () => {
    expect(isSafeSquare(4, 4)).toBe(true);
  });

  it('returns false for a normal board cell', () => {
    expect(isSafeSquare(3, 3)).toBe(false);
    expect(isSafeSquare(5, 5)).toBe(false);
  });

  it('returns false for an off-board cell', () => {
    expect(isSafeSquare(0, 0)).toBe(false);
  });
});

describe('getCellType', () => {
  it('returns "center" for (4, 4)', () => {
    expect(getCellType(4, 4)).toBe('center');
  });

  it('returns "safe" for safe squares that are not the center', () => {
    // (0,4) is safe but not center
    expect(getCellType(0, 4)).toBe('safe');
    expect(getCellType(4, 0)).toBe('safe');
    expect(getCellType(8, 4)).toBe('safe');
  });

  it('returns "home_red" for cells in the top arm (rows 0-2, cols 3-5) that are not safe', () => {
    // (1, 3) is in red home and is not a safe square
    expect(getCellType(1, 3)).toBe('home_red');
    expect(getCellType(2, 3)).toBe('home_red');
    expect(getCellType(0, 3)).toBe('home_red');
  });

  it('returns "home_blue" for cells in the right arm', () => {
    expect(getCellType(3, 7)).toBe('home_blue');
    expect(getCellType(4, 7)).toBe('home_blue');
  });

  it('returns "home_green" for cells in the bottom arm that are not safe', () => {
    expect(getCellType(7, 3)).toBe('home_green');
    expect(getCellType(6, 3)).toBe('home_green');
  });

  it('returns "home_yellow" for cells in the left arm that are not safe', () => {
    expect(getCellType(3, 0)).toBe('home_yellow');
    expect(getCellType(5, 1)).toBe('home_yellow');
  });

  it('returns "normal" for cross cells not in any special category', () => {
    // (3, 3) is the intersection corner — normal
    expect(getCellType(3, 3)).toBe('normal');
    expect(getCellType(5, 5)).toBe('normal');
  });

  it('center takes priority over safe squares', () => {
    // (4,4) is both in SAFE_SQUARES and is CENTER_CELL; center wins
    expect(getCellType(4, 4)).toBe('center');
  });

  it('safe takes priority over home zone', () => {
    // (0,4) is a safe square AND in the red home zone; safe wins
    expect(getCellType(0, 4)).toBe('safe');
  });
});

describe('HOME_ZONES', () => {
  it('contains zones for all four players', () => {
    const players = HOME_ZONES.map((z) => z.player);
    expect(players).toContain('red');
    expect(players).toContain('blue');
    expect(players).toContain('green');
    expect(players).toContain('yellow');
  });

  it('each zone contains exactly 9 cells', () => {
    for (const zone of HOME_ZONES) {
      expect(zone.cells).toHaveLength(9);
    }
  });

  it('all home zone cells are valid board cells', () => {
    for (const zone of HOME_ZONES) {
      for (const { row, col } of zone.cells) {
        expect(isBoardCell(row, col)).toBe(true);
      }
    }
  });
});

describe('cellTo3D', () => {
  it('maps the center cell (4,4) to (0, 0, 0)', () => {
    const [x, y, z] = cellTo3D(4, 4);
    expect(x).toBeCloseTo(0);
    expect(y).toBe(0);
    expect(z).toBeCloseTo(0);
  });

  it('returns y = 0 for all cells (board lies on the XZ plane)', () => {
    const [, y] = cellTo3D(0, 3);
    expect(y).toBe(0);
  });

  it('adjacent cells differ in position by SQUARE_STEP', () => {
    const [x1] = cellTo3D(4, 3);
    const [x2] = cellTo3D(4, 4);
    expect(x2 - x1).toBeCloseTo(SQUARE_STEP);
  });

  it('row axis maps to z; column axis maps to x', () => {
    const [x1, , z1] = cellTo3D(3, 4);
    const [x2, , z2] = cellTo3D(4, 3);
    // Moving down one row → z increases
    expect(z1).toBeLessThan(z2);
    // Moving right one column → x increases
    expect(x2).toBeLessThan(x1);
  });
});
