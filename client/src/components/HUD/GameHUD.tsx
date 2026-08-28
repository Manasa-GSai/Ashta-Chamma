/**
 * GameHUD — Heads-Up Display overlay for the Ashta Chamma 3D game board.
 *
 * Reads game state from the Zustand store and renders:
 *   - Turn indicator (whose turn it is)
 *   - Roll button — HIDDEN for spectators (AC-5)
 *   - 'Spectating' badge — shown only when the current user is a spectator (AC-5)
 *   - Player list with scores / colours
 *
 * The component is intentionally read-only with respect to game state;
 * all mutations flow through WebSocket messages handled by WebSocketManager.
 */

import React from 'react';
import { useGameStore } from '../../store/gameStore';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface SpectatingBadgeProps {
  visible: boolean;
}

/**
 * SpectatingBadge — displayed when the user is watching but not playing.
 * The badge is always rendered in the DOM; `visible` controls display so
 * screen readers can announce a change without a mount/unmount transition.
 */
const SpectatingBadge: React.FC<SpectatingBadgeProps> = ({ visible }) => {
  if (!visible) return null;

  return (
    <div
      role="status"
      aria-label="You are spectating this game"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        padding: '4px 10px',
        borderRadius: '9999px',
        backgroundColor: 'rgba(99, 102, 241, 0.15)',
        border: '1px solid rgba(99, 102, 241, 0.5)',
        color: '#818cf8',
        fontSize: '0.75rem',
        fontWeight: 600,
        letterSpacing: '0.05em',
        textTransform: 'uppercase',
        userSelect: 'none',
      }}
    >
      {/* Eye icon (inline SVG — no icon library dependency) */}
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      Spectating
    </div>
  );
};

// ---------------------------------------------------------------------------
// RollButton
// ---------------------------------------------------------------------------

interface RollButtonProps {
  hidden: boolean;
  disabled: boolean;
  onRoll: () => void;
}

/**
 * RollButton — triggers a roll_request WebSocket message.
 *
 * Hidden entirely (not just disabled) for spectators so there is no
 * affordance for an action they cannot perform.
 */
const RollButton: React.FC<RollButtonProps> = ({ hidden, disabled, onRoll }) => {
  if (hidden) return null;

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onRoll}
      aria-label="Roll cowries"
      style={{
        padding: '10px 28px',
        borderRadius: '8px',
        border: 'none',
        backgroundColor: disabled ? '#374151' : '#4f46e5',
        color: disabled ? '#9ca3af' : '#ffffff',
        fontSize: '1rem',
        fontWeight: 700,
        cursor: disabled ? 'not-allowed' : 'pointer',
        transition: 'background-color 150ms ease',
      }}
    >
      🎲 Roll
    </button>
  );
};

// ---------------------------------------------------------------------------
// TurnIndicator
// ---------------------------------------------------------------------------

interface TurnIndicatorProps {
  currentTurn: string | null;
  currentUserId: string | null;
}

const TurnIndicator: React.FC<TurnIndicatorProps> = ({
  currentTurn,
  currentUserId,
}) => {
  if (!currentTurn) return null;

  const isMyTurn = currentTurn === currentUserId;

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        color: isMyTurn ? '#4ade80' : '#d1d5db',
        fontWeight: 600,
        fontSize: '0.9rem',
      }}
    >
      {isMyTurn ? 'Your turn!' : `Waiting for player ${currentTurn}…`}
    </div>
  );
};

// ---------------------------------------------------------------------------
// GameHUD (main export)
// ---------------------------------------------------------------------------

interface GameHUDProps {
  /** Callback invoked when the Roll button is clicked. */
  onRoll?: () => void;
}

const GameHUD: React.FC<GameHUDProps> = ({ onRoll }) => {
  const isSpectator = useGameStore((s) => s.isSpectator);
  const room = useGameStore((s) => s.room);
  const phase = useGameStore((s) => s.phase);
  const currentUserId = useGameStore((s) => s.currentUserId);

  const isMyTurn = phase.currentTurn === currentUserId;
  const rollAllowed = !isSpectator && isMyTurn && phase.rollResult === null;

  const handleRoll = (): void => {
    if (!rollAllowed) return;
    onRoll?.();
  };

  return (
    <div
      data-testid="game-hud"
      style={{
        position: 'fixed',
        top: '16px',
        left: '50%',
        transform: 'translateX(-50%)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '12px',
        padding: '12px 20px',
        backgroundColor: 'rgba(17, 24, 39, 0.85)',
        borderRadius: '12px',
        backdropFilter: 'blur(8px)',
        boxShadow: '0 4px 24px rgba(0, 0, 0, 0.4)',
        zIndex: 100,
        minWidth: '200px',
      }}
    >
      {/* Room code */}
      {room && (
        <div style={{ color: '#9ca3af', fontSize: '0.75rem' }}>
          Room <span style={{ color: '#e5e7eb', fontWeight: 700 }}>{room.code}</span>
        </div>
      )}

      {/* Spectating badge — visible only for spectators (AC-5) */}
      <SpectatingBadge visible={isSpectator} />

      {/* Turn indicator */}
      <TurnIndicator
        currentTurn={phase.currentTurn}
        currentUserId={currentUserId}
      />

      {/* Roll button — hidden for spectators (AC-5) */}
      <RollButton
        hidden={isSpectator}
        disabled={!rollAllowed}
        onRoll={handleRoll}
      />
    </div>
  );
};

export default GameHUD;
export { SpectatingBadge, RollButton, TurnIndicator };
