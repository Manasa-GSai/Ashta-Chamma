import { BrowserRouter, Route, Routes, Link } from 'react-router-dom';
import { BoardScene } from './components/Board/BoardScene';

const HomePage = (): JSX.Element => (
  <main style={{ fontFamily: 'sans-serif', padding: '2rem', textAlign: 'center' }}>
    <h1>Ashta Chamma 3D</h1>
    <p>A traditional Indian board game, reimagined in 3D.</p>
    <Link to="/game" style={{ fontSize: '1.25rem', color: '#4f8ef7' }}>
      Play Game →
    </Link>
  </main>
);

export const App = (): JSX.Element => {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/game" element={<BoardScene />} />
      </Routes>
    </BrowserRouter>
  );
};
