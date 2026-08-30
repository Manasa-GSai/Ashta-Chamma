import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WebSocketManager } from '../services/WebSocketManager';

// ---------------------------------------------------------------------------
// Minimal in-memory WebSocket stub — enough to exercise the manager logic.
// ---------------------------------------------------------------------------

type StoredListener = (event: Event) => void;

const createMockSocket = (): {
  readyState: number;
  sentMessages: string[];
  addEventListener: (type: string, listener: StoredListener) => void;
  removeEventListener: (type: string, listener: StoredListener) => void;
  send: (data: string) => void;
  close: () => void;
  simulateOpen: () => void;
  simulateMessage: (data: Record<string, unknown>) => void;
  simulateClose: () => void;
} => {
  const listenerMap = new Map<string, StoredListener[]>();
  const sentMessages: string[] = [];

  const emit = (type: string, event: Event): void => {
    const listeners = listenerMap.get(type) ?? [];
    listeners.forEach((l) => l(event));
  };

  return {
    readyState: 0,
    sentMessages,
    addEventListener(type: string, listener: StoredListener): void {
      const existing = listenerMap.get(type) ?? [];
      listenerMap.set(type, [...existing, listener]);
    },
    removeEventListener(type: string, listener: StoredListener): void {
      const existing = listenerMap.get(type) ?? [];
      listenerMap.set(
        type,
        existing.filter((l) => l !== listener),
      );
    },
    send(data: string): void {
      sentMessages.push(data);
    },
    close(): void {
      this.readyState = 3;
      emit('close', new Event('close'));
    },
    simulateOpen(): void {
      this.readyState = 1;
      emit('open', new Event('open'));
    },
    simulateMessage(data: Record<string, unknown>): void {
      const event = { data: JSON.stringify(data) } as MessageEvent<string>;
      emit('message', event as unknown as Event);
    },
    simulateClose(): void {
      this.close();
    },
  };
};

describe('WebSocketManager', () => {
  let manager: WebSocketManager;
  let mockSocket: ReturnType<typeof createMockSocket>;
  let MockWebSocketCtor: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    WebSocketManager.resetInstance();
    manager = WebSocketManager.getInstance();
    mockSocket = createMockSocket();
    MockWebSocketCtor = vi.fn().mockImplementation(() => mockSocket);
    Object.assign(MockWebSocketCtor, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
    vi.stubGlobal('WebSocket', MockWebSocketCtor);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    WebSocketManager.resetInstance();
  });

  it('passes the JWT token as a query parameter in the WebSocket URL', () => {
    manager.connect('room-42', 'jwt-abc');
    expect(MockWebSocketCtor).toHaveBeenCalledWith(
      expect.stringContaining('token=jwt-abc'),
    );
  });

  it('includes the room ID in the WebSocket URL', () => {
    manager.connect('room-42', 'jwt-abc');
    expect(MockWebSocketCtor).toHaveBeenCalledWith(
      expect.stringContaining('/rooms/room-42'),
    );
  });

  it('dispatches incoming messages to registered handlers', () => {
    const handler = vi.fn();
    const unsubscribe = manager.onMessage(handler);
    manager.connect('r1', 'tok');
    mockSocket.simulateOpen();

    mockSocket.simulateMessage({ type: 'state_update', state: { turn: 2 } });

    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith('state_update', { state: { turn: 2 } });
    unsubscribe();
  });

  it('sends serialised JSON messages when the socket is open', () => {
    manager.connect('r1', 'tok');
    mockSocket.simulateOpen();
    manager.send('roll_request');

    expect(mockSocket.sentMessages).toEqual([JSON.stringify({ type: 'roll_request' })]);
  });

  it('removes a handler when the unsubscribe function is called', () => {
    const handler = vi.fn();
    const unsubscribe = manager.onMessage(handler);
    unsubscribe();

    manager.connect('r1', 'tok');
    mockSocket.simulateOpen();
    mockSocket.simulateMessage({ type: 'ping' });

    expect(handler).not.toHaveBeenCalled();
  });

  it('reports isConnected as false before connecting', () => {
    expect(manager.isConnected).toBe(false);
  });
});
