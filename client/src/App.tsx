import { useCallback } from 'react';
import { ChatPanel } from './components/Chat/ChatPanel';
import { useGameStore } from './store/gameStore';

export const App = (): JSX.Element => {
  const addChatMessage = useGameStore((s) => s.addChatMessage);

  /**
   * Placeholder WebSocket send handler.  A real implementation (added in the
   * WebSocket manager work order) will forward the text over the active
   * WebSocket connection.  On receipt of a 'chat_broadcast' server message the
   * caller should invoke addChatMessage() to update the store.
   */
  const handleSendMessage = useCallback(
    (_text: string) => {
      // TODO(WO-016): replace with WebSocketManager.send({ type: 'chat', text })
      // For demonstration, echo the message back locally.
      addChatMessage({
        timestamp: new Date().toISOString(),
        senderName: 'You',
        senderColor: '#4a9eed',
        text: _text,
      });
    },
    [addChatMessage],
  );

  return (
    <main>
      <h1>Ashta Chamma 3D</h1>
      <p>Monorepo scaffold initialized. Game implementation coming soon.</p>
      <ChatPanel sendMessage={handleSendMessage} />
    </main>
  );
};
