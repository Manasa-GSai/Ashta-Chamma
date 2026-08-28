import { useRef, useEffect, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { ScreenReaderAnnouncer } from '../Accessibility/ScreenReaderAnnouncer';
import { useKeyboardPawnSelection, type Pawn } from '../../hooks/useKeyboardPawnSelection';

/** Phases of the game that affect HUD rendering and focus management. */
export type GamePhase = 'rolling' | 'selecting' | 'game_over';

/** Alias kept for external consumers who import PawnInfo from this module. */
export type PawnInfo = Pawn;

export interface PlayerInfo {
  id: string;
  name: string;
  /** CSS colour string — must pass WCAG 4.5:1 contrast against the background. */
  color: string;
  score: number;
}

export interface GameHUDProps {
  /** The player whose turn it currently is. */
  currentPlayer: PlayerInfo;
  /** True when it is the local user's turn (enables roll/select controls). */
  isCurrentUserTurn: boolean;
  /** Current game phase driving which controls are visible. */
  phase: GamePhase;
  /** Most recent cowrie roll value; triggers 'Rolled [value]' announcement. */
  rollValue?: number;
  /**
   * Human-readable move description for the last completed move,
   * e.g. '[Color] pawn moved to [position]'.
   */
  lastMoveDescription?: string;
  /**
   * Human-readable capture description,
   * e.g. '[Color] captured [Color] pawn'.
   */
  captureDescription?: string;
  /** Winner's display name; triggers win announcement and focuses result. */
  winnerName?: string;
  /** Legal pawns the current user may select; empty if no legal moves. */
  legalPawns: PawnInfo[];
  /** All players in the game for the score display. */
  players: PlayerInfo[];
  onRoll: () => void;
  onSelectPawn: (pawnId: number) => void;
}

/**
 * Game heads-up display with full WCAG 2.1 AA keyboard navigation and
 * screen reader announcement support.
 *
 * Focus management:
 * - When it becomes the user's turn to roll, focus moves to the Roll button.
 * - When it becomes the user's turn to select a pawn (after roll), focus moves
 *   to the pawn selection group.
 * - On game over, focus moves to the result alert element.
 *
 * Screen reader announcements (via ScreenReaderAnnouncer):
 * - 'Your turn to roll' when it is the user's turn in rolling phase
 * - 'Rolled [value]' after a roll result arrives
 * - '[Color] pawn moved to [position]' after a move (via lastMoveDescription)
 * - '[Color] captured [Color] pawn' on capture (via captureDescription)
 * - '[Color] player wins!' on game over
 */
export const GameHUD = ({
  currentPlayer,
  isCurrentUserTurn,
  phase,
  rollValue,
  lastMoveDescription,
  captureDescription,
  winnerName,
  legalPawns,
  players,
  onRoll,
  onSelectPawn,
}: GameHUDProps): JSX.Element => {
  const rollButtonRef = useRef<HTMLButtonElement>(null);
  const pawnGroupRef = useRef<HTMLDivElement>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const [announcement, setAnnouncement] = useState<string>('');

  const handleSelectPawn = (pawn: Pawn) => {
    onSelectPawn(pawn.id);
  };

  const { focusedPawnIndex, handleKeyDown, resetFocus } =
    useKeyboardPawnSelection(legalPawns, handleSelectPawn);

  // Announce: whose turn it is
  useEffect(() => {
    if (isCurrentUserTurn && phase === 'rolling') {
      setAnnouncement('Your turn to roll');
    } else if (!isCurrentUserTurn && phase === 'rolling') {
      setAnnouncement(`${currentPlayer.name}'s turn to roll`);
    }
  }, [isCurrentUserTurn, phase, currentPlayer.name]);

  // Announce: roll result
  useEffect(() => {
    if (rollValue !== undefined) {
      setAnnouncement(`Rolled ${rollValue}`);
    }
  }, [rollValue]);

  // Announce: move completed
  useEffect(() => {
    if (lastMoveDescription) {
      setAnnouncement(lastMoveDescription);
    }
  }, [lastMoveDescription]);

  // Announce: capture event
  useEffect(() => {
    if (captureDescription) {
      setAnnouncement(captureDescription);
    }
  }, [captureDescription]);

  // Announce: game over
  useEffect(() => {
    if (winnerName) {
      setAnnouncement(`${winnerName} player wins!`);
    }
  }, [winnerName]);

  // Focus management: Roll button when it is user's turn to roll
  useEffect(() => {
    if (isCurrentUserTurn && phase === 'rolling' && rollButtonRef.current) {
      rollButtonRef.current.focus();
    }
  }, [isCurrentUserTurn, phase]);

  // Focus management: Pawn group when user must select a pawn
  useEffect(() => {
    if (isCurrentUserTurn && phase === 'selecting' && pawnGroupRef.current) {
      pawnGroupRef.current.focus();
      resetFocus();
    }
  }, [isCurrentUserTurn, phase, resetFocus]);

  // Focus management: Result element on game over
  useEffect(() => {
    if (phase === 'game_over' && resultRef.current) {
      resultRef.current.focus();
    }
  }, [phase]);

  const handleRollKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
  ) => {
    // Buttons already activate on Enter natively; add Space for consistency
    // with WCAG 2.1 SC 2.1.1 requirement that all functionality is keyboard operable.
    if (event.key === ' ') {
      event.preventDefault();
      onRoll();
    }
  };

  return (
    <div role="region" aria-label="Game HUD">
      {/* Visually hidden live region for screen reader announcements */}
      <ScreenReaderAnnouncer message={announcement} />

      {/* Turn indicator */}
      <div role="status" aria-label="Current turn indicator">
        <span>
          {isCurrentUserTurn ? 'Your turn' : `${currentPlayer.name}'s turn`}
        </span>
      </div>

      {/* Score board */}
      <section aria-label="Player scores">
        <ul role="list">
          {players.map((player) => (
            <li key={player.id} role="listitem">
              {/*
               * Color alone must not be the only differentiator (WCAG 1.4.1).
               * Player name is always shown; aria-label provides full context.
               */}
              <span
                aria-label={`${player.name}: ${player.score} point${player.score !== 1 ? 's' : ''}`}
              >
                {player.name}: {player.score}
              </span>
            </li>
          ))}
        </ul>
      </section>

      {/* Roll button — only visible during user's rolling phase */}
      {phase === 'rolling' && isCurrentUserTurn && (
        <button
          ref={rollButtonRef}
          type="button"
          onClick={onRoll}
          onKeyDown={handleRollKeyDown}
          aria-label="Roll cowrie shells"
        >
          Roll
        </button>
      )}

      {/* Pawn selection — only visible during user's selecting phase */}
      {phase === 'selecting' && isCurrentUserTurn && legalPawns.length > 0 && (
        <div
          ref={pawnGroupRef}
          role="group"
          aria-label="Select a pawn to move. Use arrow keys to navigate, Enter to select."
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          {legalPawns.map((pawn, index) => (
            <button
              key={pawn.id}
              type="button"
              onClick={() => onSelectPawn(pawn.id)}
              aria-label={`Move ${pawn.color} pawn at position ${pawn.position}`}
              aria-current={index === focusedPawnIndex ? 'true' : undefined}
              tabIndex={index === focusedPawnIndex ? 0 : -1}
            >
              {pawn.color} pawn
            </button>
          ))}
        </div>
      )}

      {/* Game over result — receives focus on game end */}
      {phase === 'game_over' && (
        <div
          ref={resultRef}
          tabIndex={-1}
          role="alert"
          aria-label={
            winnerName ? `${winnerName} player wins!` : 'Game over'
          }
        >
          {winnerName ? `${winnerName} wins!` : 'Game over'}
        </div>
      )}
    </div>
  );
};
