import { SignIn as ClerkSignIn } from '@clerk/clerk-react';

/**
 * Sign-in page using Clerk's pre-built component.
 * Supports Google OAuth and email/password authentication (configured in Clerk dashboard).
 */
export const SignIn = (): JSX.Element => {
  return (
    <main style={{ display: 'flex', justifyContent: 'center', paddingTop: '4rem' }}>
      <ClerkSignIn
        path="/sign-in"
        routing="path"
        signUpUrl="/sign-up"
        fallbackRedirectUrl="/lobby"
      />
    </main>
  );
};
