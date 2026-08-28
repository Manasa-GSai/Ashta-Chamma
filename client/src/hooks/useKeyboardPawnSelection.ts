import { useState, useCallback } from 'react';
import type { KeyboardEvent } from 'react';

export interface Pawn {
  id: number;
  color: string;
  position: number;
}

export interface UseKeyboardPawnSelectionResult {
  /** Index of the currently keyboard-focused pawn within the legalPawns array. */
  focusedPawnIndex: number;
  /**
   * keyDown handler to attach to the pawn selection container.
   * Arrow keys cycle through legal pawns; Enter selects the focused pawn.
   * Handled keys call stopPropagation to prevent interference with 3D canvas
   * orbit-control key bindings.
   */
  handleKeyDown: (event: KeyboardEvent) => void;
  /** Imperatively set the focused pawn index (e.g., on mouse hover). */
  setFocusedPawnIndex: (index: number) => void;
  /** Reset focus to the first pawn — call after a pawn is selected. */
  resetFocus: () => void;
}

/**
 * Provides keyboard navigation for pawn selection in the game HUD.
 *
 * Keyboard controls:
 * - ArrowRight / ArrowDown: move focus to next legal pawn (wraps around)
 * - ArrowLeft  / ArrowUp:   move focus to previous legal pawn (wraps around)
 * - Enter:                  select the currently focused pawn
 *
 * The hook calls stopPropagation on all handled key events to prevent
 * those keys from reaching the Three.js orbit-control listener underneath.
 */
export const useKeyboardPawnSelection = (
  legalPawns: Pawn[],
  onSelectPawn: (pawn: Pawn) => void,
): UseKeyboardPawnSelectionResult => {
  const [focusedPawnIndex, setFocusedPawnIndex] = useState<number>(0);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      if (legalPawns.length === 0) return;

      switch (event.key) {
        case 'ArrowRight':
        case 'ArrowDown': {
          event.preventDefault();
          event.stopPropagation();
          setFocusedPawnIndex((prev) => (prev + 1) % legalPawns.length);
          break;
        }
        case 'ArrowLeft':
        case 'ArrowUp': {
          event.preventDefault();
          event.stopPropagation();
          setFocusedPawnIndex(
            (prev) => (prev - 1 + legalPawns.length) % legalPawns.length,
          );
          break;
        }
        case 'Enter': {
          event.preventDefault();
          event.stopPropagation();
          const selectedPawn = legalPawns[focusedPawnIndex];
          if (selectedPawn !== undefined) {
            onSelectPawn(selectedPawn);
          }
          break;
        }
        default:
          break;
      }
    },
    [legalPawns, focusedPawnIndex, onSelectPawn],
  );

  const resetFocus = useCallback(() => setFocusedPawnIndex(0), []);

  return { focusedPawnIndex, handleKeyDown, setFocusedPawnIndex, resetFocus };
};
