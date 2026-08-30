type MessageHandler = (message: unknown) => void;

/** All messages the client may send to the server. */
export type OutboundMessage =
  | { type: 'select_pawn'; pawn_id: string }
  | { type: 'roll_request' }
  | { type: 'chat'; text: string }
  | { type: 'ping' };

/**
 * Singleton WebSocket wrapper that manages the persistent connection to the
 * game server.  Components interact via `send()` and `addMessageHandler()`.
 * The singleton is intentionally module-level so that all components share
 * the same connection; tests can reset it via `reset()`.
 */
class WebSocketManager {
  private _socket: WebSocket | null = null;
  private _messageHandlers: Set<MessageHandler> = new Set();

  connect(url: string): void {
    if (this._socket) {
      this._socket.close();
    }
    this._socket = new WebSocket(url);
    this._socket.addEventListener('message', (event) => {
      try {
        const message = JSON.parse(event.data as string) as unknown;
        this._messageHandlers.forEach((handler) => handler(message));
      } catch {
        // Silently ignore unparseable frames — server always sends JSON.
      }
    });
  }

  send(message: OutboundMessage): void {
    if (!this._socket || this._socket.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocketManager] Cannot send — socket not open');
      return;
    }
    this._socket.send(JSON.stringify(message));
  }

  addMessageHandler(handler: MessageHandler): void {
    this._messageHandlers.add(handler);
  }

  removeMessageHandler(handler: MessageHandler): void {
    this._messageHandlers.delete(handler);
  }

  disconnect(): void {
    this._socket?.close();
    this._socket = null;
  }

  /** Replace the internal socket — used in tests to inject a mock. */
  _setSocket(socket: WebSocket | null): void {
    this._socket = socket;
  }

  get isConnected(): boolean {
    return this._socket?.readyState === WebSocket.OPEN;
  }
}

export const webSocketManager = new WebSocketManager();
