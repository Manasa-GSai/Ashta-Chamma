import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('@clerk/clerk-react', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '@clerk/clerk-react';
import { ProtectedRoute } from './ProtectedRoute';

const mockUseAuth = vi.mocked(useAuth);

/**
 * ProtectedRoute is a React Router v6 layout route — child routes render via
 * <Outlet />.  The test renders it as the element of a parent <Route> wrapping
 * a protected child route, matching how it is used in production.
 */
const renderWithRouter = (initialPath = '/protected') => {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/sign-in" element={<div>Sign In Page</div>} />
        <Route element={<ProtectedRoute />}>
          <Route path="/protected" element={<div>Protected Content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
};

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('when auth is loaded and user is signed in', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isSignedIn: true,
        isLoaded: true,
      } as unknown as ReturnType<typeof useAuth>);
    });

    it('renders the protected child route', () => {
      renderWithRouter('/protected');
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });

    it('does not show a loading indicator', () => {
      renderWithRouter('/protected');
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  describe('when auth is loaded and user is not signed in', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
      } as unknown as ReturnType<typeof useAuth>);
    });

    it('redirects to /sign-in and does not render the child route', () => {
      renderWithRouter('/protected');
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
      expect(screen.getByText('Sign In Page')).toBeInTheDocument();
    });
  });

  describe('when auth is still loading', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isSignedIn: undefined,
        isLoaded: false,
      } as unknown as ReturnType<typeof useAuth>);
    });

    it('renders a loading indicator', () => {
      renderWithRouter('/protected');
      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('does not render the child route while loading', () => {
      renderWithRouter('/protected');
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });
});
