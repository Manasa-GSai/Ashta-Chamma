import { memo } from 'react';
import { useGameStore } from '../../store/gameStore';
import { Pawn3D } from './Pawn3D';

/**
 * PawnManager is a React Three Fiber scene component that owns all 16 pawn models.
 *
 * Responsibilities:
 *  - Reads pawn state from the Zustand game store (subscribes to changes)
 *  - Renders one Pawn3D per pawn (16 total: 4 colors × 4 pawns)
 *  - Provides a stable key for each pawn so React can track identity through moves
 *
 * This component intentionally contains no animation logic — animation is
 * encapsulated in each Pawn3D via the usePawnAnimation hook.
 *
 * Placement: render this component inside an R3F <Canvas> after all lighting
 * is set up, e.g. alongside Board3D.
 */
export const PawnManager = memo(() => {
  const pawns = useGameStore((state) => state.pawns);

  return (
    <group name="pawn-manager">
      {pawns.map((pawn) => (
        <Pawn3D key={pawn.id} pawn={pawn} />
      ))}
    </group>
  );
});

PawnManager.displayName = 'PawnManager';
