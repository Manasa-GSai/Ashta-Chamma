import { type JSX } from 'react';
import { useAuth } from '@clerk/clerk-react';
import { Navigate, Outlet } from 'react-router-dom';

/**
 * React Router v6 layout route that enforces authentication.
 * Usage: wrap protected <Route> definitions as children of this element.
 *
 * <Route element={<ProtectedRoute />}>
 *   <Route path="/dashboard" element={<Dashboard />} />
 * </Route>
 *
 * Unauthenticated users are redirected to /sign-in.
 * While Clerk is resolving auth status an accessible loading indicator renders.
 */
export const ProtectedRoute = (): JSX.Element => {
  const { isSignedIn, isLoaded } = useAuth();

  if (!isLoaded) {
    return <div aria-label="Loading">Loading...</div>;
  }

  if (!isSignedIn) {
    return <Navigate to="/sign-in" replace />;
  }

  return <Outlet />;
};
