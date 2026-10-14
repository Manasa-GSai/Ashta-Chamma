import { memo } from 'react';
import { cellTo3D, type CellType, SQUARE_SIZE, SQUARE_HEIGHT } from '../../constants/board';

interface SquareProps {
  readonly row: number;
  readonly col: number;
  readonly cellType: CellType;
}

/** Hex colour for each cell type. Warm wood palette with distinct player colours. */
const CELL_COLOR: Record<CellType, string> = {
  normal: '#c8a96e',
  safe: '#f5c842',
  center: '#e63946',
  home_red: '#ff6b6b',
  home_blue: '#4f8ef7',
  home_green: '#6bcb77',
  home_yellow: '#ffd166',
};

/** PBR roughness per cell type — shiny for special squares, matte for wood. */
const CELL_ROUGHNESS: Record<CellType, number> = {
  normal: 0.85,
  safe: 0.4,
  center: 0.25,
  home_red: 0.65,
  home_blue: 0.65,
  home_green: 0.65,
  home_yellow: 0.65,
};

/** PBR metalness per cell type. */
const CELL_METALNESS: Record<CellType, number> = {
  normal: 0.05,
  safe: 0.3,
  center: 0.4,
  home_red: 0.1,
  home_blue: 0.1,
  home_green: 0.1,
  home_yellow: 0.1,
};

/**
 * Renders a single board square as a BoxGeometry with MeshStandardMaterial.
 * Memoised to avoid re-renders when unrelated parent state changes.
 */
const SquareComponent = ({ row, col, cellType }: SquareProps): JSX.Element => {
  const [x, y, z] = cellTo3D(row, col);

  return (
    <mesh position={[x, y, z]} receiveShadow>
      <boxGeometry args={[SQUARE_SIZE, SQUARE_HEIGHT, SQUARE_SIZE]} />
      <meshStandardMaterial
        color={CELL_COLOR[cellType]}
        roughness={CELL_ROUGHNESS[cellType]}
        metalness={CELL_METALNESS[cellType]}
      />
    </mesh>
  );
};

export const Square = memo(SquareComponent);
