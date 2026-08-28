import { useRef, useState, useCallback } from 'react';
import { type Mesh, Color } from 'three';
import { type ThreeEvent } from '@react-three/fiber';
import { useGameStore } from '../../store/gameStore';
import { webSocketManager } from '../../websocket/WebSocketManager';

export interface Pawn3DProps {
  pawnId: number;
  position: [number, number, number];
  /** CSS/hex color string for the pawn body — one per player. */
  color: string;
}

/** Warm amber glow applied to selectable pawns. */
const HIGHLIGHT_COLOR = new Color(0xffaa00);
const DEFAULT_COLOR = new Color(0x000000);
const HIGHLIGHT_INTENSITY = 1.5;
const HOVER_INTENSITY = 2.1;
const DEFAULT_INTENSITY = 0;

/**
 * 3D pawn mesh rendered with React Three Fiber.
 *
 * Selection behaviour:
 *  - When the server sends move_options, the Zustand store transitions to
 *    SELECTING and populates legalMoveIds.  Any Pawn3D whose pawnId is in
 *    legalMoveIds becomes "selectable" and receives an emissive glow.
 *  - Clicking a selectable pawn dispatches `{type: "select_pawn", pawn_id}`
 *    via WebSocket, clears selection state, and transitions to MOVING.
 *  - Non-selectable pawns absorb no pointer events (stopPropagation guard).
 */
export const Pawn3D = ({ pawnId, position, color }: Pawn3DProps): JSX.Element => {
  const meshRef = useRef<Mesh>(null);
  const [isHovered, setIsHovered] = useState(false);

  const legalMoveIds = useGameStore((state) => state.legalMoveIds);
  const gamePhase = useGameStore((state) => state.gamePhase);
  const clearSelection = useGameStore((state) => state.clearSelection);
  const setGamePhase = useGameStore((state) => state.setGamePhase);

  /** True only when this specific pawn is in the current legal move list. */
  const isSelectable = legalMoveIds.includes(pawnId) && gamePhase === 'SELECTING';

  const handlePointerDown = useCallback(
    (event: ThreeEvent<PointerEvent>) => {
      if (!isSelectable) return;
      // Prevent the board / scene from also receiving this click.
      event.stopPropagation();
      webSocketManager.send({ type: 'select_pawn', pawn_id: pawnId });
      // Clear highlights immediately so the UI responds before the server reply.
      clearSelection();
      setGamePhase('MOVING');
    },
    [isSelectable, pawnId, clearSelection, setGamePhase],
  );

  const handlePointerOver = useCallback(
    (event: ThreeEvent<PointerEvent>) => {
      if (!isSelectable) return;
      event.stopPropagation();
      setIsHovered(true);
      document.body.style.cursor = 'pointer';
    },
    [isSelectable],
  );

  const handlePointerOut = useCallback(() => {
    setIsHovered(false);
    document.body.style.cursor = 'default';
  }, []);

  const emissiveColor = isSelectable ? HIGHLIGHT_COLOR : DEFAULT_COLOR;
  const emissiveIntensity = isSelectable
    ? isHovered
      ? HOVER_INTENSITY
      : HIGHLIGHT_INTENSITY
    : DEFAULT_INTENSITY;

  return (
    <mesh
      ref={meshRef}
      position={position}
      onPointerDown={handlePointerDown}
      onPointerOver={handlePointerOver}
      onPointerOut={handlePointerOut}
    >
      {/* Slightly wider base for stability, 16-sided cylinder for roundness */}
      <cylinderGeometry args={[0.3, 0.35, 0.6, 16]} />
      <meshStandardMaterial
        color={color}
        emissive={emissiveColor}
        emissiveIntensity={emissiveIntensity}
      />
    </mesh>
  );
};
