import { memo, useMemo } from 'react';
import { getBoardCells, getCellType } from '../../constants/board';
import { Square } from './Square';

/**
 * Renders all 45 squares of the cross-shaped Ashta Chamma board.
 * Each square is positioned in 3D world space via cellTo3D().
 * The cell list is computed once via useMemo and never re-calculated.
 */
const Board3DComponent = (): JSX.Element => {
  const cells = useMemo(() => getBoardCells(), []);

  return (
    <group>
      {cells.map(({ row, col }) => (
        <Square
          key={`${row}-${col}`}
          row={row}
          col={col}
          cellType={getCellType(row, col)}
        />
      ))}
    </group>
  );
};

export const Board3D = memo(Board3DComponent);
