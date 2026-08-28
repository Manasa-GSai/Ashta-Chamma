import { useEffect } from 'react';
import { WebSocketManager } from '../services/WebSocketManager';
import { useGameStore } from '../store/gameStore';
import type { ConnectionState } from '../store/gameStore';

export interface UseWebSocketReturn {
  connectionState: ConnectionState;
  reconnectAttempts: number;
  connectionError: string | null;
  isConnected: boolean;
  send: WebSocketManager['send'];
  onMessage: WebSocketManager['onMessage'];
  reconnect: () => void;
}

/**
 * React hook that initialises and owns the lifecycle of the WebSocketManager
 * for a given room. Connects on mount, disconnects on unmount.
 *
 * @param roomId  - The room the client wants to join (included in the WSS URL).
 * @param token   - A valid Clerk JWT for the connecting user. When falsy the
 *                  connection is deferred until a non-empty value is provided.
 */
export const useWebSocket = (roomId: string, token: string): UseWebSocketReturn => {
  useEffect(() => {
    // Defer connection until we have a valid token (e.g. Clerk loading state)
    if (!token) {
      return;
    }

    const manager = WebSocketManager.getInstance();
    manager.connect(roomId, token);

    return () => {
      // Disconnect when the component unmounts or the roomId/token changes
      manager.disconnect();
    };
  }, [roomId, token]);

  const connectionState = useGameStore((s) => s.connectionState);
  const reconnectAttempts = useGameStore((s) => s.reconnectAttempts);
  const connectionError = useGameStore((s) => s.connectionError);

  const manager = WebSocketManager.getInstance();

  return {
    connectionState,
    reconnectAttempts,
    connectionError,
    isConnected: manager.isConnected,
    send: manager.send.bind(manager),
    onMessage: manager.onMessage.bind(manager),
    reconnect: () => useGameStore.getState().triggerManualReconnect(),
  };
};
