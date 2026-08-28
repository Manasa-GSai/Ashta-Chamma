import { ClerkProvider } from '@clerk/clerk-react';
import type { ReactNode } from 'react';

interface AuthProviderProps {
  children: ReactNode;
}

// Loaded from VITE_CLERK_PUBLISHABLE_KEY — never hard-code the key here.
const publishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY;

if (!publishableKey) {
  throw new Error(
    'Missing VITE_CLERK_PUBLISHABLE_KEY environment variable. ' +
      'Add it to your .env file before starting the development server.',
  );
}

/**
 * Wraps the application with Clerk's authentication context.
 * All child components can access auth state via Clerk's hooks.
 */
export const AuthProvider = ({ children }: AuthProviderProps): JSX.Element => {
  return <ClerkProvider publishableKey={publishableKey}>{children}</ClerkProvider>;
};
