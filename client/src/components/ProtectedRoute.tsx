import { type JSX } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Navigate } from 'react-router-dom';

interface ProtectedRouteProps {
  children: JSX.Element;
}

/**
 * Wraps a route that requires authentication.
 * Redirects unauthenticated users to /login and shows a loading
 * indicator while Clerk determines auth status.
 */
export const ProtectedRoute = ({ children }: ProtectedRouteProps): JSX.Element => {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) {
    return <div aria-label="Loading">Loading...</div>;
  }

  if (!isSignedIn) {
    return <Navigate to="/login" replace />;
  }

  return children;
};
