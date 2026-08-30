import { memo } from 'react';
import { useGameStore } from '../../store/gameStore';
import { gridToWorld } from '../../utils/gridToWorld';
import { Pawn3D } from './Pawn3D';

/**
 * PawnManager is a React Three Fiber scene component that owns all 16 pawn models.
 *
 * Responsibilities:
 *  - Reads pawn state from the Zustand game store (subscribes to changes)
 *  - Renders one Pawn3D per pawn (16 total: 4 colors × 4 pawns)
 *  - Provides a stable key for each pawn so React can track identity through moves
 *
 * Placement: render this component inside an R3F <Canvas> after all lighting
 * is set up, e.g. alongside Board3D.
 */
export const PawnManager = memo(() => {
  const pawns = useGameStore((state) => state.pawns);

  return (
    <group name="pawn-manager">
      {pawns.map((pawn) => {
        const worldPos = gridToWorld(pawn.gridPosition.row, pawn.gridPosition.col);
        return (
          <Pawn3D
            key={pawn.id}
            pawnId={pawn.id}
            position={[worldPos.x, worldPos.y, worldPos.z]}
            // PlayerColor values ('RED', 'GREEN', etc.) are valid lowercase CSS colors.
            color={pawn.color.toLowerCase()}
          />
        );
      })}
    </group>
  );
});

PawnManager.displayName = 'PawnManager';
