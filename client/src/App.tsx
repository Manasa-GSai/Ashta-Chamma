import { useState } from 'react';
import { MainMenu } from './pages/MainMenu';
import { Lobby } from './pages/Lobby';

type AppPage = 'menu' | 'lobby';

/**
 * Root application component providing top-level page routing.
 * Uses simple string-based page state rather than a router library so the
 * navigation model remains transparent during the early build phase.
 *
 * Accessibility note: page transitions do not reload the document, so focus
 * must be managed explicitly — each page component moves focus to its primary
 * landmark on mount.
 */
export const App = (): JSX.Element => {
  const [page, setPage] = useState<AppPage>('menu');

  if (page === 'lobby') {
    return (
      <Lobby
        players={[]}
        isHost={true}
        isReady={false}
        canStart={false}
        onCreateRoom={() => {
          /* room creation wired in by the game-session WO */
        }}
        onJoinRoom={() => {
          /* join logic wired in by the game-session WO */
        }}
        onToggleReady={() => {
          /* ready-toggle wired in by the game-session WO */
        }}
        onStartGame={() => {
          /* start-game wired in by the game-session WO */
        }}
        onLeave={() => setPage('menu')}
      />
    );
  }

  return (
    <MainMenu
      onNewGame={() => setPage('lobby')}
      onJoinGame={() => setPage('lobby')}
      onSettings={() => {
        /* settings wired in by the settings WO */
      }}
    />
  );
};
