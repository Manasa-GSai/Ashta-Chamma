import { describe, it, expect, vi, beforeEach, afterEach, type Mock } from 'vitest';
import { WebSocketManager } from '../WebSocketManager';
import { useGameStore } from '../../store/gameStore';

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

/**
 * Minimal WebSocket mock that exposes helpers for test-driven state simulation.
 * Stored in MockWebSocket.instances so tests can access the latest socket.
 */
class MockWebSocket {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState: number = MockWebSocket.CONNECTING;
  url: string;

  onopen: ((event: Event) => void) | null = null;
  onclose: ((event: CloseEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent) => void) | null = null;

  /** Messages passed to send() in order. */
  sentMessages: string[] = [];

  static instances: MockWebSocket[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sentMessages.push(data);
  }

  close(): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code: 1000 }));
  }

  // Helpers to drive test scenarios ----------------------------------------

  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    this.onopen?.(new Event('open'));
  }

  simulateMessage(data: unknown): void {
    this.onmessage?.(
      new MessageEvent('message', { data: JSON.stringify(data) }),
    );
  }

  simulateClose(code = 1006): void {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.(new CloseEvent('close', { code }));
  }

  simulateError(): void {
    this.onerror?.(new Event('error'));
  }

  static reset(): void {
    MockWebSocket.instances = [];
  }

  /** Convenience: the most-recently constructed instance. */
  static get latest(): MockWebSocket {
    const inst = MockWebSocket.instances.at(-1);
    if (!inst) throw new Error('No MockWebSocket instances exist');
    return inst;
  }
}

// Patch the global WebSocket with our mock for all tests in this file
vi.stubGlobal('WebSocket', MockWebSocket);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStore() {
  return useGameStore.getState();
}

function resetStore() {
  useGameStore.setState({
    connectionState: 'disconnected',
    reconnectAttempts: 0,
    connectionError: null,
    lastRollResult: null,
    gameState: null,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('WebSocketManager', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    MockWebSocket.reset();
    WebSocketManager.resetInstance();
    resetStore();
  });

  afterEach(() => {
    vi.useRealTimers();
    WebSocketManager.resetInstance();
  });

  // -------------------------------------------------------------------------
  // Singleton
  // -------------------------------------------------------------------------

  describe('singleton', () => {
    it('returns the same instance on repeated calls', () => {
      const a = WebSocketManager.getInstance();
      const b = WebSocketManager.getInstance();
      expect(a).toBe(b);
    });

    it('creates a fresh instance after resetInstance()', () => {
      const a = WebSocketManager.getInstance();
      WebSocketManager.resetInstance();
      const b = WebSocketManager.getInstance();
      expect(a).not.toBe(b);
    });
  });

  // -------------------------------------------------------------------------
  // connect() — URL construction
  // -------------------------------------------------------------------------

  describe('connect()', () => {
    it('opens a WebSocket with the correct wss URL including JWT token', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('room-42', 'jwt-token-abc');

      expect(MockWebSocket.instances).toHaveLength(1);
      const ws = MockWebSocket.latest;
      expect(ws.url).toContain('ws/rooms/room-42');
      expect(ws.url).toContain('token=jwt-token-abc');
      expect(ws.url).toMatch(/^wss:\/\//);
    });

    it('URL-encodes the JWT token', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('room-1', 'tok+en/=');
      expect(MockWebSocket.latest.url).toContain(encodeURIComponent('tok+en/='));
    });

    it('sets connectionState to "connecting" immediately', () => {
      WebSocketManager.getInstance().connect('r', 'tok');
      expect(getStore().connectionState).toBe('connecting');
    });

    it('is a no-op when already connected to the same room', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('room-1', 'tok');
      MockWebSocket.latest.simulateOpen();
      const countBefore = MockWebSocket.instances.length;

      manager.connect('room-1', 'tok');
      expect(MockWebSocket.instances.length).toBe(countBefore);
    });

    it('closes the old socket and opens a new one for a different room', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('room-1', 'tok');
      MockWebSocket.latest.simulateOpen();
      manager.connect('room-2', 'tok');
      expect(MockWebSocket.instances).toHaveLength(2);
    });
  });

  // -------------------------------------------------------------------------
  // send()
  // -------------------------------------------------------------------------

  describe('send()', () => {
    it('serialises the message as JSON with type field', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      manager.send('roll_request');
      expect(MockWebSocket.latest.sentMessages).toHaveLength(1);
      const parsed = JSON.parse(MockWebSocket.latest.sentMessages[0] as string) as Record<
        string,
        unknown
      >;
      expect(parsed['type']).toBe('roll_request');
    });

    it('merges payload fields into the top-level JSON object', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      manager.send('select_pawn', { pawn_id: 3 });
      const parsed = JSON.parse(MockWebSocket.latest.sentMessages[0] as string) as Record<
        string,
        unknown
      >;
      expect(parsed['type']).toBe('select_pawn');
      expect(parsed['pawn_id']).toBe(3);
    });

    it('does not send when socket is not OPEN and logs a warning', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      // Socket is still CONNECTING — do not simulate open

      manager.send('roll_request');
      expect(MockWebSocket.latest.sentMessages).toHaveLength(0);
      expect(warnSpy).toHaveBeenCalled();
      warnSpy.mockRestore();
    });
  });

  // -------------------------------------------------------------------------
  // Received messages — dispatch to store
  // -------------------------------------------------------------------------

  describe('message dispatch to store', () => {
    it('dispatches roll_result to updateRoll in the store', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      MockWebSocket.latest.simulateMessage({
        type: 'roll_result',
        value: 4,
        cowries: [true, true, false, true],
      });

      expect(getStore().lastRollResult).toEqual({
        value: 4,
        cowries: [true, true, false, true],
      });
    });

    it('dispatches game_state_update to updateGameState in the store', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      MockWebSocket.latest.simulateMessage({
        type: 'game_state_update',
        board: [0, 1, 2],
      });

      expect(getStore().gameState).toMatchObject({ board: [0, 1, 2] });
    });

    it('dispatches state_update (alias) to updateGameState', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      MockWebSocket.latest.simulateMessage({ type: 'state_update', turn: 2 });
      expect(getStore().gameState).toMatchObject({ turn: 2 });
    });

    it('dispatches server error to setError in the store', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      MockWebSocket.latest.simulateMessage({
        type: 'error',
        code: 'NOT_YOUR_TURN',
        message: 'It is not your turn.',
      });

      expect(getStore().connectionError).toBe('It is not your turn.');
    });

    it('ignores messages with invalid JSON', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      const ws = MockWebSocket.latest;
      ws.simulateOpen();

      ws.onmessage?.(new MessageEvent('message', { data: 'not-json{{{' }));
      // Store should be unchanged
      expect(getStore().lastRollResult).toBeNull();
      expect(warnSpy).toHaveBeenCalled();
      warnSpy.mockRestore();
    });

    it('ignores messages missing a type field', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      MockWebSocket.latest.simulateMessage({ value: 42 }); // no type
      expect(getStore().lastRollResult).toBeNull();
      expect(warnSpy).toHaveBeenCalled();
      warnSpy.mockRestore();
    });

    it('calls registered onMessage handlers with type and payload', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      const handler: Mock = vi.fn();
      manager.onMessage(handler);

      MockWebSocket.latest.simulateMessage({ type: 'chat', from: 'alice', text: 'hi' });
      expect(handler).toHaveBeenCalledWith('chat', { from: 'alice', text: 'hi' });
    });

    it('unsubscribes handler after calling the returned cleanup function', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      const handler: Mock = vi.fn();
      const unsub = manager.onMessage(handler);
      unsub();

      MockWebSocket.latest.simulateMessage({ type: 'chat', text: 'hello' });
      expect(handler).not.toHaveBeenCalled();
    });
  });

  // -------------------------------------------------------------------------
  // Reconnection — exponential backoff
  // -------------------------------------------------------------------------

  describe('reconnection with exponential backoff', () => {
    it('sets state to "reconnecting" on unexpected close', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      MockWebSocket.latest.simulateClose();

      expect(getStore().connectionState).toBe('reconnecting');
    });

    it('attempt 1 waits 1 000 ms before reconnecting', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      MockWebSocket.latest.simulateClose();

      expect(MockWebSocket.instances).toHaveLength(1);
      vi.advanceTimersByTime(999);
      expect(MockWebSocket.instances).toHaveLength(1);

      vi.advanceTimersByTime(1);
      expect(MockWebSocket.instances).toHaveLength(2);
    });

    it('attempt 2 waits 2 000 ms (doubling)', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      // First failure
      MockWebSocket.latest.simulateClose();
      vi.advanceTimersByTime(1000);
      // Second failure — reconnect opened but close it again
      expect(MockWebSocket.instances).toHaveLength(2);
      MockWebSocket.latest.simulateClose();

      // Should now wait 2 000 ms
      vi.advanceTimersByTime(1999);
      expect(MockWebSocket.instances).toHaveLength(2);
      vi.advanceTimersByTime(1);
      expect(MockWebSocket.instances).toHaveLength(3);
    });

    it('increments reconnectAttempts in the store on each attempt', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      MockWebSocket.latest.simulateClose();

      expect(getStore().reconnectAttempts).toBe(1);

      vi.advanceTimersByTime(1000);
      MockWebSocket.latest.simulateClose();
      expect(getStore().reconnectAttempts).toBe(2);
    });

    it('sends state_recovery_request after reconnecting', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      MockWebSocket.latest.simulateClose();

      vi.advanceTimersByTime(1000);
      MockWebSocket.latest.simulateOpen(); // reconnect succeeds

      const messages = MockWebSocket.latest.sentMessages;
      expect(messages.length).toBeGreaterThanOrEqual(1);
      const recovery = JSON.parse(messages[0] as string) as Record<string, unknown>;
      expect(recovery['type']).toBe('state_recovery_request');
    });

    it('resets reconnectAttempts and shows connected state on successful reconnect', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      MockWebSocket.latest.simulateClose();

      vi.advanceTimersByTime(1000);
      MockWebSocket.latest.simulateOpen();

      expect(getStore().connectionState).toBe('connected');
      expect(getStore().reconnectAttempts).toBe(0);
    });
  });

  // -------------------------------------------------------------------------
  // Max retry limit
  // -------------------------------------------------------------------------

  describe('max reconnect attempts (5)', () => {
    it('sets disconnected state and a user-friendly error after 5 failures', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      // Simulate 5 consecutive failures with escalating backoff
      const delays = [1000, 2000, 4000, 8000, 16000];
      for (const delay of delays) {
        MockWebSocket.latest.simulateClose();
        vi.advanceTimersByTime(delay);
      }

      // 5th close triggers the "give up" path (no more timer fires)
      MockWebSocket.latest.simulateClose();

      expect(getStore().connectionState).toBe('disconnected');
      expect(getStore().connectionError).toMatch(/reconnect/i);
    });

    it('does not schedule another reconnect after max attempts', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      const delays = [1000, 2000, 4000, 8000, 16000];
      for (const delay of delays) {
        MockWebSocket.latest.simulateClose();
        vi.advanceTimersByTime(delay);
      }
      MockWebSocket.latest.simulateClose(); // 6th close — should be ignored

      const countAfterExhaustion = MockWebSocket.instances.length;
      vi.advanceTimersByTime(60_000); // no further reconnect should happen
      expect(MockWebSocket.instances.length).toBe(countAfterExhaustion);
    });
  });

  // -------------------------------------------------------------------------
  // disconnect()
  // -------------------------------------------------------------------------

  describe('disconnect()', () => {
    it('closes the WebSocket and sets state to disconnected', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      manager.disconnect();
      expect(getStore().connectionState).toBe('disconnected');
    });

    it('does not attempt to reconnect after explicit disconnect', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      manager.disconnect();

      const countAfterDisconnect = MockWebSocket.instances.length;
      vi.advanceTimersByTime(60_000);
      expect(MockWebSocket.instances.length).toBe(countAfterDisconnect);
    });

    it('cancels a pending reconnect timer', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();
      MockWebSocket.latest.simulateClose(); // starts timer

      manager.disconnect();
      const countAtDisconnect = MockWebSocket.instances.length;
      vi.advanceTimersByTime(2000);
      expect(MockWebSocket.instances.length).toBe(countAtDisconnect);
    });
  });

  // -------------------------------------------------------------------------
  // Manual reconnect (UI button)
  // -------------------------------------------------------------------------

  describe('manual reconnect via store triggerManualReconnect()', () => {
    it('resets attempt count and opens a new connection', () => {
      const manager = WebSocketManager.getInstance();
      manager.connect('r', 't');
      MockWebSocket.latest.simulateOpen();

      // Exhaust all retries
      const delays = [1000, 2000, 4000, 8000, 16000];
      for (const delay of delays) {
        MockWebSocket.latest.simulateClose();
        vi.advanceTimersByTime(delay);
      }
      MockWebSocket.latest.simulateClose();

      expect(getStore().connectionState).toBe('disconnected');
      const countBefore = MockWebSocket.instances.length;

      // User clicks "Reconnect"
      useGameStore.getState().triggerManualReconnect();

      expect(MockWebSocket.instances.length).toBe(countBefore + 1);
      expect(getStore().connectionState).toBe('connecting');
    });
  });
});
