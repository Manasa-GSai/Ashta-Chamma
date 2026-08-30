/**
 * Tests for Pawn3D selection interaction.
 *
 * React Three Fiber renders to a WebGL canvas unavailable in jsdom.
 * We mock @react-three/fiber so its JSX elements fall through as plain HTML,
 * and mock `three` so `new Color(...)` is a plain object.
 *
 * Core behaviours under test:
 *   1. Only pawns in legalMoveIds + SELECTING phase are selectable.
 *   2. Clicking a selectable pawn sends `{type: "select_pawn", pawn_id}` via WS.
 *   3. Clicking a non-selectable pawn does nothing.
 *   4. After selection, clearSelection() removes all legal move IDs.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, fireEvent } from '@testing-library/react';
import { useGameStore } from '../../store/gameStore';
import { GamePhase } from '../../store/types';
import { webSocketManager } from '../../websocket/WebSocketManager';

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

vi.mock('three', () => {
  class MockColor {
    hex: number | string;
    constructor(hex: number | string) {
      this.hex = hex;
    }
  }
  return { Color: MockColor };
});

vi.mock('@react-three/fiber', () => ({}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const resetStore = () =>
  useGameStore.setState({
    gamePhase: GamePhase.WAITING,
    legalMoveIds: [],
    moveOptions: [],
  });

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

  it('renders without error when pawn is NOT in legalMoveIds', async () => {
    const Pawn3D = await getPawn3D();
    const { container } = render(
      <Pawn3D pawnId="R1" position={[0, 0, 0]} color="#ff0000" />,
    );
    expect(container).toBeTruthy();
  });

  it('renders without error when pawn IS in legalMoveIds (SELECTING phase)', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'R1', target_pos: 5 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);
    const { container } = render(
      <Pawn3D pawnId="R1" position={[0, 0, 0]} color="#ff0000" />,
    );
    expect(container).toBeTruthy();
  });

  it('sends select_pawn message when a selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'R2', target_pos: 8 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="R2" position={[0, 0, 0]} color="#0000ff" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(webSocketManager.send).toHaveBeenCalledOnce();
    expect(webSocketManager.send).toHaveBeenCalledWith({
      type: 'select_pawn',
      pawn_id: 'R2',
    });
  });

  it('sends the correct pawn_id for the clicked pawn', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([
      { pawn_id: 'R1', target_pos: 5 },
      { pawn_id: 'G3', target_pos: 10 },
    ]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="G3" position={[1, 0, 1]} color="#00ff00" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    const sentMessage = (webSocketManager.send as ReturnType<typeof vi.fn>).mock
      .calls[0][0] as { type: string; pawn_id: string };
    expect(sentMessage.pawn_id).toBe('G3');
  });

  it('does NOT send a WebSocket message when a non-selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'R1', target_pos: 2 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="B2" position={[2, 0, 2]} color="#ffffff" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(webSocketManager.send).not.toHaveBeenCalled();
  });

  it('does NOT send a message when gamePhase is ROLLING even if pawnId is listed', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.setState({
      gamePhase: GamePhase.ROLLING,
      legalMoveIds: ['R1'],
      moveOptions: [{ pawn_id: 'R1', target_pos: 3 }],
    });

    const { container } = render(
      <Pawn3D pawnId="R1" position={[0, 0, 0]} color="#ff0000" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(webSocketManager.send).not.toHaveBeenCalled();
  });

  it('clears legalMoveIds and moveOptions after a selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'Y4', target_pos: 6 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="Y4" position={[0, 0, 0]} color="#ff8800" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    const state = useGameStore.getState();
    expect(state.legalMoveIds).toHaveLength(0);
    expect(state.moveOptions).toHaveLength(0);
  });

  it('transitions gamePhase to MOVING after a selectable pawn is clicked', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'Y4', target_pos: 6 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="Y4" position={[0, 0, 0]} color="#ff8800" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerDown(meshEl);

    expect(useGameStore.getState().gamePhase).toBe(GamePhase.MOVING);
  });

  it('sets cursor to pointer on hover over a selectable pawn', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'G1', target_pos: 11 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="G1" position={[0, 0, 0]} color="#aabbcc" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerOver(meshEl);

    expect(document.body.style.cursor).toBe('pointer');
  });

  it('resets cursor to default on pointer out', async () => {
    const Pawn3D = await getPawn3D();
    useGameStore.getState().setMoveOptions([{ pawn_id: 'G1', target_pos: 11 }]);
    useGameStore.getState().setGamePhase(GamePhase.SELECTING);

    const { container } = render(
      <Pawn3D pawnId="G1" position={[0, 0, 0]} color="#aabbcc" />,
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
      <Pawn3D pawnId="B4" position={[0, 0, 0]} color="#111111" />,
    );

    const meshEl = container.firstElementChild as HTMLElement;
    fireEvent.pointerOver(meshEl);

    expect(document.body.style.cursor).toBe('default');
  });
});
