import { render, screen } from '@testing-library/react';
import { type ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock Clerk so tests run without a ClerkProvider
vi.mock('@clerk/clerk-react', () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from '@clerk/clerk-react';
import { ProtectedRoute } from './ProtectedRoute';

// Helper to cast the mock so TypeScript is happy
const mockUseAuth = vi.mocked(useAuth);

const renderWithRouter = (ui: ReactElement, initialPath = '/') => {
  return render(<MemoryRouter initialEntries={[initialPath]}>{ui}</MemoryRouter>);
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
      } as ReturnType<typeof useAuth>);
    });

    it('renders the child element', () => {
      renderWithRouter(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>,
      );
      expect(screen.getByText('Protected Content')).toBeInTheDocument();
    });

    it('does not show a loading indicator', () => {
      renderWithRouter(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>,
      );
      expect(screen.queryByText(/loading/i)).not.toBeInTheDocument();
    });
  });

  describe('when auth is loaded and user is not signed in', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isSignedIn: false,
        isLoaded: true,
      } as ReturnType<typeof useAuth>);
    });

    it('does not render the child element', () => {
      renderWithRouter(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>,
        '/protected',
      );
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });

    it('redirects (Navigate is rendered instead of children)', () => {
      renderWithRouter(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>,
        '/protected',
      );
      // The child should not be visible — Navigate replaces it
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });

  describe('when auth is still loading', () => {
    beforeEach(() => {
      mockUseAuth.mockReturnValue({
        isSignedIn: false,
        isLoaded: false,
      } as ReturnType<typeof useAuth>);
    });

    it('renders a loading indicator', () => {
      renderWithRouter(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>,
      );
      expect(screen.getByText(/loading/i)).toBeInTheDocument();
    });

    it('does not render the child element while loading', () => {
      renderWithRouter(
        <ProtectedRoute>
          <div>Protected Content</div>
        </ProtectedRoute>,
      );
      expect(screen.queryByText('Protected Content')).not.toBeInTheDocument();
    });
  });
});
