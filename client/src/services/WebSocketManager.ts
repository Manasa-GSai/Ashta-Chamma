// Base URL for WebSocket connections. Defaults to the same host over WSS.
const WS_BASE_URL: string = import.meta.env.VITE_WS_BASE_URL ?? 'wss://localhost:8000';

export interface WebSocketMessage {
  type: string;
  [key: string]: unknown;
}

type MessageHandler = (message: WebSocketMessage) => void;

/**
 * Manages the WebSocket connection to a game room.
 *
 * - Accepts the Clerk JWT at connect time; the token is sent as a query
 *   parameter on the initial upgrade request (validated once by the server).
 * - Implements exponential back-off reconnection so transient network drops
 *   are recovered transparently.
 * - Event handlers are registered by message type for clean separation
 *   of concerns in consuming components.
 */
export class WebSocketManager {
  private _socket: WebSocket | null = null;
  private _handlers = new Map<string, MessageHandler[]>();
  private _reconnectDelay = 1000;
  private readonly _maxReconnectDelay = 30_000;
  private _currentRoomId: string | null = null;
  private _currentToken: string | null = null;

  /**
   * Opens a WebSocket connection to the specified room, authenticating
   * with the supplied Clerk JWT.
   */
  connect(roomId: string, token: string): void {
    this._currentRoomId = roomId;
    this._currentToken = token;
    const url = `${WS_BASE_URL}/ws/rooms/${roomId}?token=${encodeURIComponent(token)}`;
    this._socket = new WebSocket(url);
    this._bindEvents();
  }

  private _bindEvents(): void {
    if (!this._socket) return;

    this._socket.addEventListener('message', (event: MessageEvent<string>) => {
      try {
        const message = JSON.parse(event.data) as WebSocketMessage;
        const handlers = this._handlers.get(message.type) ?? [];
        handlers.forEach((h) => h(message));
      } catch {
        // Ignore non-JSON frames (ping frames, etc.)
      }
    });

    this._socket.addEventListener('close', () => {
      this._scheduleReconnect();
    });
  }

  private _scheduleReconnect(): void {
    setTimeout(() => {
      if (this._currentRoomId !== null && this._currentToken !== null) {
        this.connect(this._currentRoomId, this._currentToken);
        // Exponential back-off capped at maxReconnectDelay.
        this._reconnectDelay = Math.min(this._reconnectDelay * 2, this._maxReconnectDelay);
      }
    }, this._reconnectDelay);
  }

  /** Register a handler for a specific message type. */
  on(type: string, handler: MessageHandler): void {
    const existing = this._handlers.get(type) ?? [];
    this._handlers.set(type, [...existing, handler]);
  }

  /** Remove a previously registered handler. */
  off(type: string, handler: MessageHandler): void {
    const existing = this._handlers.get(type) ?? [];
    this._handlers.set(
      type,
      existing.filter((h) => h !== handler),
    );
  }

  /** Send a message to the server. No-ops if the socket is not open. */
  send(message: WebSocketMessage): void {
    if (this._socket?.readyState === WebSocket.OPEN) {
      this._socket.send(JSON.stringify(message));
    }
  }

  /** Close the connection and reset state. */
  disconnect(): void {
    this._socket?.close();
    this._socket = null;
    this._currentRoomId = null;
    this._currentToken = null;
    this._reconnectDelay = 1000;
  }
}

/** Singleton instance shared across the application. */
export const webSocketManager = new WebSocketManager();
