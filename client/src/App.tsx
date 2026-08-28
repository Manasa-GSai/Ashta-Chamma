import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { NavBar } from './components/NavBar';
import { ProtectedRoute } from './components/ProtectedRoute';
import { SignIn } from './pages/SignIn';
import { SignUp } from './pages/SignUp';
import { AuthProvider } from './providers/AuthProvider';

// Placeholder pages — replaced by full implementations in later work orders.
const Lobby = (): JSX.Element => (
  <main>
    <h1>Lobby</h1>
    <p>Game lobby — coming soon.</p>
  </main>
);

const Game = (): JSX.Element => (
  <main>
    <h1>Game</h1>
    <p>3D game board — coming soon.</p>
  </main>
);

export const App = (): JSX.Element => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <NavBar />
        <Routes>
          {/* Public auth routes */}
          <Route path="/sign-in/*" element={<SignIn />} />
          <Route path="/sign-up/*" element={<SignUp />} />

          {/* Protected routes — redirect to /sign-in when unauthenticated */}
          <Route element={<ProtectedRoute />}>
            <Route path="/lobby" element={<Lobby />} />
            <Route path="/game" element={<Game />} />
          </Route>

          {/* Default: redirect root to /lobby (ProtectedRoute handles auth check) */}
          <Route path="/" element={<Navigate to="/lobby" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};
