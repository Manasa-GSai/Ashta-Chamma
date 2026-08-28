import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Game } from './pages/Game';
import { Lobby } from './pages/Lobby';
import { MainMenu } from './pages/MainMenu';
import { Rules } from './pages/Rules';

export const App = (): JSX.Element => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/lobby" element={<Lobby />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/game/:code" element={<Game />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};
