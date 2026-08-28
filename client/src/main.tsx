import { ClerkProvider } from '@clerk/clerk-react';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
import { App } from './App';
import i18n from './i18n';

const clerkPublishableKey = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as
  | string
  | undefined;

if (!clerkPublishableKey) {
  // Allow the app to load in development without Clerk configured,
  // but log a clear warning for operators.
  console.warn(
    '[AshtaChamma] VITE_CLERK_PUBLISHABLE_KEY is not set. ' +
      'Authentication features will not work.',
  );
}

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found in index.html');
}

const content = (
  <I18nextProvider i18n={i18n}>
    <App />
  </I18nextProvider>
);

createRoot(rootElement).render(
  <StrictMode>
    {clerkPublishableKey ? (
      <ClerkProvider publishableKey={clerkPublishableKey}>
        {content}
      </ClerkProvider>
    ) : (
      content
    )}
  </StrictMode>,
);
