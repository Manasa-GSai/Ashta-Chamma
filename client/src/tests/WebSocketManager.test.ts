import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { WebSocketManager, type WebSocketMessage } from '../services/WebSocketManager';

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
  simulateMessage: (data: WebSocketMessage) => void;
} => {
  const listenerMap = new Map<string, StoredListener[]>();
  const sentMessages: string[] = [];

  return {
    readyState: 1, // equivalent to WebSocket.OPEN
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
      this.readyState = 3; // WebSocket.CLOSED
    },
    simulateMessage(data: WebSocketMessage): void {
      const listeners = listenerMap.get('message') ?? [];
      const event = { data: JSON.stringify(data) } as MessageEvent<string>;
      listeners.forEach((l) => l(event as unknown as Event));
    },
  };
};

describe('WebSocketManager', () => {
  let manager: WebSocketManager;
  let mockSocket: ReturnType<typeof createMockSocket>;
  let MockWebSocketCtor: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    manager = new WebSocketManager();
    mockSocket = createMockSocket();
    MockWebSocketCtor = vi.fn().mockImplementation(() => mockSocket);
    // Attach static constants so WebSocketManager can read WebSocket.OPEN.
    Object.assign(MockWebSocketCtor, { CONNECTING: 0, OPEN: 1, CLOSING: 2, CLOSED: 3 });
    vi.stubGlobal('WebSocket', MockWebSocketCtor);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    manager.disconnect();
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

  it('dispatches incoming messages to registered handlers by type', () => {
    const handler = vi.fn();
    manager.on('state_update', handler);
    manager.connect('r1', 'tok');

    mockSocket.simulateMessage({ type: 'state_update', state: { turn: 2 } });

    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith({ type: 'state_update', state: { turn: 2 } });
  });

  it('ignores messages intended for other handler types', () => {
    const handler = vi.fn();
    manager.on('roll_result', handler);
    manager.connect('r1', 'tok');

    mockSocket.simulateMessage({ type: 'state_update' });

    expect(handler).not.toHaveBeenCalled();
  });

  it('sends serialised JSON messages when the socket is open', () => {
    manager.connect('r1', 'tok');
    manager.send({ type: 'roll_request' });

    expect(mockSocket.sentMessages).toEqual([JSON.stringify({ type: 'roll_request' })]);
  });

  it('removes a specific handler when off() is called', () => {
    const handler = vi.fn();
    manager.on('ping', handler);
    manager.off('ping', handler);
    manager.connect('r1', 'tok');

    mockSocket.simulateMessage({ type: 'ping' });

    expect(handler).not.toHaveBeenCalled();
  });
});
