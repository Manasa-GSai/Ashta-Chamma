import { useGameStore } from '../../store/gameStore';

/** World-space side length of one board grid square. */
const SQUARE_SIZE = 1;

/**
 * Tiny Y offset above the board surface to prevent z-fighting with the board
 * geometry itself.
 */
const HIGHLIGHT_Y = 0.01;

/**
 * Maps a linear board position index to a world-space x/z coordinate pair.
 *
 * The Ashta Chamma board is a 7×7 cross-shaped grid.  The outer ring and
 * the inner cross arm squares are the playable track.  Position 0 is the
 * entry square closest to the board centre for player 1.
 *
 * NOTE: This mapping is a placeholder that must be kept in sync with the
 * BoardRenderer geometry.  The x/z formula treats the board as a flat 7×7
 * grid centred at origin and will be replaced by the precise path mapping
 * once BoardRenderer is implemented (WO-019).
 */
function boardPositionToWorld(pos: number): { x: number; z: number } {
  const col = pos % 7;
  const row = Math.floor(pos / 7);
  return {
    x: (col - 3) * SQUARE_SIZE,
    z: (row - 3) * SQUARE_SIZE,
  };
}

/**
 * Renders a semi-transparent green overlay on every destination square for
 * the current turn's legal moves.  Only visible during the SELECTING phase.
 *
 * One overlay per MoveOption is rendered so that if two different pawns can
 * land on the same square they both produce an overlay (deduplication is
 * intentionally avoided — overlapping translucent planes increase brightness,
 * which is desirable visual feedback).
 */
export const DestinationHighlight = (): JSX.Element | null => {
  const moveOptions = useGameStore((state) => state.moveOptions);
  const gamePhase = useGameStore((state) => state.gamePhase);

  if (gamePhase !== 'SELECTING' || moveOptions.length === 0) {
    return null;
  }

  return (
    <>
      {moveOptions.map(({ pawn_id, target_pos }) => {
        const { x, z } = boardPositionToWorld(target_pos);
        return (
          <mesh
            key={`dest-${pawn_id}-${target_pos}`}
            position={[x, HIGHLIGHT_Y, z]}
            // Plane geometry faces up (+Y) but Three.js planes face +Z by default;
            // rotate -90° around X to lay it flat on the board.
            rotation={[-Math.PI / 2, 0, 0]}
          >
            <planeGeometry args={[SQUARE_SIZE * 0.9, SQUARE_SIZE * 0.9]} />
            <meshStandardMaterial
              color="#00ff88"
              transparent
              opacity={0.45}
              // Avoid writing to depth buffer so underlying board squares stay visible.
              depthWrite={false}
            />
          </mesh>
        );
      })}
    </>
  );
};
