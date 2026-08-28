import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { useAuth } from '@clerk/clerk-react';
import { ProtectedRoute } from '../components/ProtectedRoute';

// Hoisted by vitest's transformer — must reference the module path exactly.
vi.mock('@clerk/clerk-react', () => ({
  useAuth: vi.fn(),
}));

// Minimal page stubs used in routing assertions.
const ProtectedPage = (): JSX.Element => <div>Protected Content</div>;
const SignInPage = (): JSX.Element => <div>Sign In Page</div>;

/**
 * Renders the ProtectedRoute with a MemoryRouter so we can simulate
 * navigation to a protected path and observe where we end up.
 */
const renderWithRouter = (initialEntry: string): void => {
  render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path="/sign-in" element={<SignInPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/protected" element={<ProtectedPage />} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
};

describe('ProtectedRoute', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('redirects unauthenticated users to /sign-in', () => {
    vi.mocked(useAuth).mockReturnValue({
      isSignedIn: false,
      isLoaded: true,
    } as unknown as ReturnType<typeof useAuth>);

    renderWithRouter('/protected');

    expect(screen.queryByText('Sign In Page')).not.toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('renders protected content for authenticated users', () => {
    vi.mocked(useAuth).mockReturnValue({
      isSignedIn: true,
      isLoaded: true,
    } as unknown as ReturnType<typeof useAuth>);

    renderWithRouter('/protected');

    expect(screen.queryByText('Protected Content')).not.toBeNull();
    expect(screen.queryByText('Sign In Page')).toBeNull();
  });

  it('shows loading indicator while auth state is being resolved', () => {
    vi.mocked(useAuth).mockReturnValue({
      isSignedIn: undefined,
      isLoaded: false,
    } as unknown as ReturnType<typeof useAuth>);

    renderWithRouter('/protected');

    expect(screen.queryByText('Loading...')).not.toBeNull();
    expect(screen.queryByText('Protected Content')).toBeNull();
    expect(screen.queryByText('Sign In Page')).toBeNull();
  });
});
