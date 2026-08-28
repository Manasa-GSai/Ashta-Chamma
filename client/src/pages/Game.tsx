import { useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { GameHUD } from '../components/HUD/GameHUD';
import { useGameStore } from '../store/gameStore';

// Placeholder canvas — replaced by the R3F BoardScene from WO-018
const BoardPlaceholder = (): JSX.Element => (
  <div
    style={{
      position: 'absolute',
      inset: 0,
      backgroundColor: '#0d0600',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      color: '#4a2800',
      fontFamily: "'Georgia', serif",
      fontSize: '1.5rem',
    }}
    aria-label="Game board loading"
  >
    {/* 3D Board rendered here by WO-018 */}
  </div>
);

export const Game = (): JSX.Element => {
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const { setRoomCode, roomCode } = useGameStore();

  // Sync route param into the store when navigating directly to /game/:code
  useEffect(() => {
    if (code !== undefined && roomCode !== code) {
      setRoomCode(code);
    }
  }, [code, roomCode, setRoomCode]);

  // Guard: if no code provided, redirect to lobby
  useEffect(() => {
    if (code === undefined) {
      void navigate('/lobby', { replace: true });
    }
  }, [code, navigate]);

  if (code === undefined) {
    return <></>;
  }

  return (
    <div
      style={{
        position: 'relative',
        width: '100vw',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: '#0d0600',
      }}
    >
      {/* 3D board canvas layer (WO-018) */}
      <BoardPlaceholder />

      {/* HUD overlay */}
      <GameHUD />
    </div>
  );
};
