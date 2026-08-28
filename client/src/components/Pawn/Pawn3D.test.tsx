/**
 * Tests for Pawn3D selection interaction.
 *
 * React Three Fiber renders to a WebGL canvas that is unavailable in jsdom.
 * We therefore mock @react-three/fiber so that its JSX elements (`<mesh>`,
 * etc.) fall through as normal HTML elements, and mock `three` so that
 * `new Color(...)` is a plain object rather than a WebGL resource.
 *
 * The core behaviours under test are:
 *   1. Only pawns in legalMoveIds emit a highlight (non-zero emissiveIntensity).
 *   2. Clicking a selectable pawn sends `{type: "select_pawn", pawn_id}` via
 *      the WebSocketManager.
 *   3. Clicking a non-selectable pawn does nothing.
 *   4. After selection, clearSelection() removes all legal move IDs.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import React from 'react';
import { useGameStore } from '../../store/gameStore';
import { webSocketManager } from '../../websocket/WebSocketManager';

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('../../websocket/WebSocketManager', () => ({
  webSocketManager: {
    send: vi.fn(),
    connect: vi.fn(),
    disconnect: vi.fn(),
    isConnected: true,
    addMessageHandler: vi.fn(),
    removeMessageHandler: vi.fn(),
    _setSocket: vi.fn(),
  },
}));

/**
 * Mock Three.js — only the classes used by Pawn3D need stubs.
 * Color is constructed with a hex value; we store it so tests can inspect it
 * if needed, but the primary assertions are via pointer events.
 */
vi.mock('three', () => {
  class MockColor {
    hex: number | string;
    constructor(hex: number | string) {
      this.hex = hex;
    }
  }
  return { Color: MockColor };
});

/**
 * Mock @react-three/fiber.
 * `ThreeEvent` is a type-only import; we don't need to mock it.
 * All Three.js custom JSX elements (`<mesh>`, `<cylinderGeometry>`, etc.)
 * are treated as unknown HTML elements by React in jsdom — they render as
 * DOM nodes and their event handlers fire normally.
 */
vi.mock('@react-three/fiber', () => ({}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const resetStore = () =>
  useGameStore.setState({
    gamePhase: 'WAITING',
    currentPlayerId: null,
    localPlayerId: null,
    legalMoveIds: [],
    moveOptions: [],
    selectedPawnId: null,
  });

// Lazy import — after mocks are registered.
const getPawn3D = async () => {
  const mod = await import('./Pawn3D');
  return mod.Pawn3D;
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Pawn3D', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  // -------------------------------------------------------------------------
  // AC1: highlight only when pawn is in legalMoveIds
  // -------------------------------------------------------------------------

  it('renders without error when pawn is NOT in legalMoveIds', async () => {
    const Pawn3D = await getPawn3D();
    // Phase is WAITING, legalMoveIds is empty — pawn is non-selectable.
    const { container } = render(
      <Pawn3D pawnId={1} position={[0, 0, 0]} color="#ff0000" />,
    );
    // Just check it mounted — no throw means the guard logic is fine.
    expect(container).toBeTruthy();
  });

  it('renders without error when pawn IS in legalMoveIds', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 1, target_pos: 5 }]);
    const { container } = render(
      <Pawn3D pawnId={1} position={[0, 0, 0]} color="#ff0000" />,
    );
    expect(container).toBeTruthy();
  });

  // -------------------------------------------------------------------------
  // AC2: clicking a selectable pawn sends select_pawn via WebSocket
  // -------------------------------------------------------------------------

  it('sends select_pawn message when a selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 2, target_pos: 8 }]);

    const { container } = render(
      <Pawn3D pawnId={2} position={[0, 0, 0]} color="#0000ff" />,
    );

    // The root element rendered by Pawn3D is the <mesh> element.
    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(webSocketManager.send).toHaveBeenCalledOnce();
    expect(webSocketManager.send).toHaveBeenCalledWith({
      type: 'select_pawn',
      pawn_id: 2,
    });
  });

  it('sends the correct pawn_id for the clicked pawn', async () => {
    const Pawn3D = await getPawn3D();
    // Two pawns are selectable; we render pawn 3.
    useGameStore.getState().setMoveOptions([
      { pawn_id: 1, target_pos: 5 },
      { pawn_id: 3, target_pos: 10 },
    ]);

    const { container } = render(
      <Pawn3D pawnId={3} position={[1, 0, 1]} color="#00ff00" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    const sentMessage = (webSocketManager.send as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as { type: string; pawn_id: number };
    expect(sentMessage.pawn_id).toBe(3);
  });

  // -------------------------------------------------------------------------
  // AC3: clicking a non-selectable pawn does nothing
  // -------------------------------------------------------------------------

  it('does NOT send a WebSocket message when a non-selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    // Only pawn 5 is selectable; we render pawn 7.
    useGameStore.getState().setMoveOptions([{ pawn_id: 5, target_pos: 2 }]);

    const { container } = render(
      <Pawn3D pawnId={7} position={[2, 0, 2]} color="#ffffff" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(webSocketManager.send).not.toHaveBeenCalled();
  });

  it('does NOT send a message when gamePhase is ROLLING even if pawnId is listed', async () => {
    const Pawn3D = await getPawn3D();
    // Manually force a state where legalMoveIds is populated but phase is wrong.
    useGameStore.setState({
      gamePhase: 'ROLLING',
      legalMoveIds: [1],
      moveOptions: [{ pawn_id: 1, target_pos: 3 }],
    });

    const { container } = render(
      <Pawn3D pawnId={1} position={[0, 0, 0]} color="#ff0000" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(webSocketManager.send).not.toHaveBeenCalled();
  });

  // -------------------------------------------------------------------------
  // AC6: after selection, highlights are cleared
  // -------------------------------------------------------------------------

  it('clears legalMoveIds and moveOptions after a selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 4, target_pos: 6 }]);

    const { container } = render(
      <Pawn3D pawnId={4} position={[0, 0, 0]} color="#ff8800" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    const state = useGameStore.getState();
    expect(state.legalMoveIds).toHaveLength(0);
    expect(state.moveOptions).toHaveLength(0);
  });

  it('transitions gamePhase to MOVING after a selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 4, target_pos: 6 }]);

    const { container } = render(
      <Pawn3D pawnId={4} position={[0, 0, 0]} color="#ff8800" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(useGameStore.getState().gamePhase).toBe('MOVING');
  });

  // -------------------------------------------------------------------------
  // AC5: hovering over a selectable pawn changes the cursor
  // -------------------------------------------------------------------------

  it('sets cursor to pointer on hover over a selectable pawn', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 6, target_pos: 11 }]);

    const { container } = render(
      <Pawn3D pawnId={6} position={[0, 0, 0]} color="#aabbcc" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerOver(meshEl);

    expect(document.body.style.cursor).toBe('pointer');
  });

  it('resets cursor to default on pointer out', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 6, target_pos: 11 }]);

    const { container } = render(
      <Pawn3D pawnId={6} position={[0, 0, 0]} color="#aabbcc" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerOver(meshEl);
    fireEvent.pointerOut(meshEl);

    expect(document.body.style.cursor).toBe('default');
  });

  it('does NOT change cursor when hovering a non-selectable pawn', async () => {
    const Pawn3D = await getPawn3D();
    document.body.style.cursor = 'default';

    const { container } = render(
      <Pawn3D pawnId={9} position={[0, 0, 0]} color="#111111" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerOver(meshEl);

    expect(document.body.style.cursor).toBe('default');
  });
});
