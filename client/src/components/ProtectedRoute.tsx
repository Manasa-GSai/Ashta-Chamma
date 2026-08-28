import { useAuth } from '@clerk/clerk-react';
import { Navigate, Outlet } from 'react-router-dom';

/**
 * Wraps a set of routes that require authentication.
 * Unauthenticated users are redirected to /sign-in.
 * Shows a loading indicator while Clerk resolves the session.
 */
export const ProtectedRoute = (): JSX.Element => {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return <div aria-label="Loading authentication">Loading...</div>;
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }

  return <Outlet />;
};
