import { SignUp as ClerkSignUp } from '@clerk/clerk-react';

/**
 * Sign-up page using Clerk's pre-built component.
 */
export const SignUp = (): JSX.Element => {
  return (
    <main style={{ display: 'flex', justifyContent: 'center', paddingTop: '4rem' }}>
      <ClerkSignUp
        path="/sign-up"
        routing="path"
        signInUrl="/sign-in"
        fallbackRedirectUrl="/lobby"
      />
    </main>
  );
};
