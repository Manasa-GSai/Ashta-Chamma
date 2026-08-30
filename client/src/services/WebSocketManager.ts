import { setReconnectCallback, useGameStore } from '../store/gameStore';
import type { GameState, RollResult } from '../store/gameStore';

export type MessagePayload = Record<string, unknown>;

/**
 * Handler registered via onMessage(). Receives the type discriminator and the
 * remaining payload fields. Handlers are used by feature modules (e.g. chat,
 * move options) that don't map directly to Zustand state.
 */
export type MessageHandler = (type: string, payload: MessagePayload) => void;

const MAX_RECONNECT_ATTEMPTS = 5;
/** Base delay in ms — doubles each attempt: 1 s, 2 s, 4 s, 8 s, 16 s → capped */
const BASE_BACKOFF_MS = 1000;
const MAX_BACKOFF_MS = 30_000;

/**
 * Singleton WebSocket manager responsible for:
 *  - Opening/closing the WSS connection to a game room
 *  - Authenticating via JWT query parameter (WebSocket API cannot set headers)
 *  - Reconnecting with exponential backoff on unexpected close/error
 *  - Parsing inbound JSON and dispatching to the Zustand store
 *  - Broadcasting raw messages to external handlers (via onMessage)
 *
 * One instance exists per room — use WebSocketManager.getInstance().
 */
class WebSocketManager {
  private static _instance: WebSocketManager | null = null;

  private _ws: WebSocket | null = null;
  private _roomId: string | null = null;
  private _token: string | null = null;

  /**
   * Counts reconnection attempts in the current failed-connection run.
   * Reset to 0 on every successful open or fresh connect() call.
   */
  private _reconnectAttempts = 0;
  private _reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  /** External message handlers registered via onMessage(). */
  private _handlers: Set<MessageHandler> = new Set();

  /**
   * True only when disconnect() is called explicitly — prevents the close
   * event from triggering the reconnection loop.
   */
  private _intentionalDisconnect = false;

  private constructor() {
    // Wire the manual-reconnect action in the Zustand store to our private method
    // so the UI button can trigger reconnection without importing this class.
    setReconnectCallback(() => {
      this._manualReconnect();
    });
  }

  /** Returns the shared WebSocketManager instance, creating it if necessary. */
  static getInstance(): WebSocketManager {
    if (!WebSocketManager._instance) {
      WebSocketManager._instance = new WebSocketManager();
    }
    return WebSocketManager._instance;
  }

  /**
   * Resets the singleton — intended for tests only.
   * Disconnects cleanly before destroying the instance.
   */
  static resetInstance(): void {
    if (WebSocketManager._instance) {
      WebSocketManager._instance.disconnect();
      // Clear the store callback so it doesn't reference a stale instance
      setReconnectCallback(null);
    }
    WebSocketManager._instance = null;
  }

  // ---------------------------------------------------------------------------
  // Public API
  // ---------------------------------------------------------------------------

  /**
   * Connects (or reconnects) to the given room.
   * If already connected to the same room, this is a no-op.
   * Passing a different roomId closes the existing connection first.
   */
  connect(roomId: string, token: string): void {
    if (
      this._ws &&
      this._roomId === roomId &&
      this._ws.readyState === WebSocket.OPEN
    ) {
      // Already connected to this room — nothing to do
      return;
    }

    // Tear down any existing connection cleanly before re-connecting
    if (this._ws) {
      this._intentionalDisconnect = true;
      this._ws.close();
      this._ws = null;
    }

    // Cancel any pending reconnect timer from a previous connection
    this._clearReconnectTimer();

    this._roomId = roomId;
    this._token = token;
    this._intentionalDisconnect = false;
    this._reconnectAttempts = 0;

    this._openConnection();
  }

  /** Closes the connection permanently (no reconnection will be attempted). */
  disconnect(): void {
    this._intentionalDisconnect = true;
    this._clearReconnectTimer();

    if (this._ws) {
      this._ws.close();
      this._ws = null;
    }

    this._roomId = null;
    this._token = null;
    this._reconnectAttempts = 0;

    useGameStore.getState().setConnectionState('disconnected');
  }

  /**
   * Sends a JSON-serialized message over the WebSocket.
   * The `type` field acts as a discriminator; `payload` is merged at top level.
   */
  send(type: string, payload: MessagePayload = {}): void {
    if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
      console.warn('[WebSocketManager] Cannot send — socket is not OPEN', { type });
      return;
    }

    const message = JSON.stringify({ type, ...payload });
    this._ws.send(message);
  }

  /**
   * Registers a handler for all inbound messages (after JSON parsing).
   * Returns an unsubscribe function for cleanup.
   */
  onMessage(handler: MessageHandler): () => void {
    this._handlers.add(handler);
    return () => {
      this._handlers.delete(handler);
    };
  }

  /** True when the underlying WebSocket is in the OPEN state. */
  get isConnected(): boolean {
    return this._ws?.readyState === WebSocket.OPEN;
  }

  // ---------------------------------------------------------------------------
  // Private helpers
  // ---------------------------------------------------------------------------

  private _openConnection(): void {
    if (!this._roomId || !this._token) {
      return;
    }

    // VITE_API_HOST is injected at build time; fall back for local dev.
    const apiHost: string =
      (import.meta.env.VITE_API_HOST as string | undefined) ?? 'localhost:8000';

    const url = `wss://${apiHost}/ws/rooms/${this._roomId}?token=${encodeURIComponent(this._token)}`;

    useGameStore.getState().setConnectionState('connecting');

    try {
      this._ws = new WebSocket(url);
    } catch (err) {
      // WebSocket constructor can throw synchronously on invalid URLs
      console.error('[WebSocketManager] Failed to create WebSocket', err);
      useGameStore
        .getState()
        .setConnectionError('Failed to create WebSocket connection. Please try again.');
      useGameStore.getState().setConnectionState('disconnected');
      return;
    }

    this._ws.onopen = this._handleOpen.bind(this);
    this._ws.onclose = this._handleClose.bind(this);
    this._ws.onerror = this._handleError.bind(this);
    this._ws.onmessage = this._handleMessage.bind(this);
  }

  private _handleOpen(): void {
    // Capture whether this was a reconnection before resetting the counter
    const wasReconnecting = this._reconnectAttempts > 0;

    this._reconnectAttempts = 0;
    this._clearReconnectTimer();

    const store = useGameStore.getState();
    store.setConnectionState('connected');
    store.setConnectionError(null);
    store.setReconnectAttempts(0);

    // After a reconnection, ask the server for a full state snapshot so the
    // client is in sync without relying on a potentially missed delta stream.
    if (wasReconnecting) {
      this.send('state_recovery_request');
    }
  }

  private _handleClose(_event: CloseEvent): void {
    if (this._intentionalDisconnect) {
      useGameStore.getState().setConnectionState('disconnected');
      return;
    }
    this._scheduleReconnect();
  }

  private _handleError(_event: Event): void {
    // In browsers an error event is always followed by a close event,
    // so reconnection is handled in _handleClose. We only update the error
    // message here so the UI has context while the close event is pending.
    useGameStore
      .getState()
      .setConnectionError('WebSocket error encountered. Attempting to reconnect…');
  }

  private _handleMessage(event: MessageEvent): void {
    let type: string;
    let payload: MessagePayload;

    try {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
      const raw: unknown = JSON.parse(event.data as string);

      if (
        typeof raw !== 'object' ||
        raw === null ||
        typeof (raw as Record<string, unknown>)['type'] !== 'string'
      ) {
        console.warn('[WebSocketManager] Ignoring message with unexpected shape', raw);
        return;
      }

      const msg = raw as { type: string } & MessagePayload;
      const { type: msgType, ...rest } = msg;
      type = msgType;
      payload = rest;
    } catch {
      console.warn('[WebSocketManager] Failed to parse message JSON', event.data);
      return;
    }

    // Route well-known types to the Zustand store
    this._dispatchToStore(type, payload);

    // Broadcast to all external handlers
    this._handlers.forEach((handler) => {
      try {
        handler(type, payload);
      } catch (err) {
        console.error('[WebSocketManager] Handler threw an error', err);
      }
    });
  }

  /**
   * Maps well-known server message types to Zustand store actions.
   * Unknown types are silently passed through to external handlers only.
   */
  private _dispatchToStore(type: string, payload: MessagePayload): void {
    const store = useGameStore.getState();

    switch (type) {
      case 'roll_result':
        store.updateRoll({
          value: payload['value'] as number,
          cowries: payload['cowries'] as boolean[],
        } satisfies RollResult);
        break;

      case 'game_state_update':
      case 'state_update':
        // Double-cast required: the wire payload is untyped Record<string, unknown>
        // but updateGameState accepts Partial<GameState>. The server is trusted to
        // send the correct shape; runtime validation would be added per WO-xxx.
        store.updateGameState(payload as unknown as Partial<GameState>);
        break;

      case 'error':
        store.setError(
          typeof payload['message'] === 'string'
            ? payload['message']
            : 'An unknown server error occurred.',
        );
        break;

      default:
        // Not dispatched to store — external handlers (chat, move_options, etc.)
        // receive it via the onMessage mechanism.
        break;
    }
  }

  private _scheduleReconnect(): void {
    if (this._reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      // Exhausted all attempts — tell the UI to show the manual reconnect button
      useGameStore.getState().setConnectionState('disconnected');
      useGameStore
        .getState()
        .setConnectionError(
          `Connection lost. Failed to reconnect after ${MAX_RECONNECT_ATTEMPTS} attempts. ` +
            'Please click "Reconnect" to try again.',
        );
      return;
    }

    this._reconnectAttempts++;

    const store = useGameStore.getState();
    store.setConnectionState('reconnecting');
    store.setReconnectAttempts(this._reconnectAttempts);
    store.setConnectionError(
      `Connection lost. Reconnecting… (attempt ${this._reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`,
    );

    // Exponential backoff: 1 s, 2 s, 4 s, 8 s, 16 s — capped at 30 s
    const delayMs = Math.min(
      BASE_BACKOFF_MS * Math.pow(2, this._reconnectAttempts - 1),
      MAX_BACKOFF_MS,
    );

    this._reconnectTimer = setTimeout(() => {
      this._openConnection();
    }, delayMs);
  }

  /** Called by the Zustand store's triggerManualReconnect action (UI button). */
  private _manualReconnect(): void {
    if (!this._roomId || !this._token) {
      return;
    }

    this._clearReconnectTimer();
    this._reconnectAttempts = 0;
    this._intentionalDisconnect = false;

    useGameStore.getState().setConnectionError(null);
    this._openConnection();
  }

  private _clearReconnectTimer(): void {
    if (this._reconnectTimer !== null) {
      clearTimeout(this._reconnectTimer);
      this._reconnectTimer = null;
    }
  }
}

export { WebSocketManager };
