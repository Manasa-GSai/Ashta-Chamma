import { SignedIn, SignedOut, UserButton } from '@clerk/clerk-react';
import { Link } from 'react-router-dom';

/**
 * Top navigation bar.
 * Shows game links and a user avatar (with sign-out dropdown) when signed in,
 * or sign-in/sign-up links when signed out.
 */
export const NavBar = (): JSX.Element => {
  return (
    <nav style={{ display: 'flex', gap: '1rem', padding: '0.75rem 1.5rem', alignItems: 'center' }}>
      <Link to="/" style={{ fontWeight: 'bold' }}>
        Ashta Chamma 3D
      </Link>

      <SignedIn>
        <Link to="/lobby">Lobby</Link>
        <Link to="/game">Game</Link>
        {/* UserButton renders user avatar and a sign-out option in its dropdown menu */}
        <UserButton afterSignOutUrl="/sign-in" />
      </SignedIn>

      <SignedOut>
        <Link to="/sign-in">Sign In</Link>
        <Link to="/sign-up">Sign Up</Link>
      </SignedOut>
    </nav>
  );
};
