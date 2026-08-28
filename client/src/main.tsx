import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';
import * as Sentry from '@sentry/react';
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

// Initialise Sentry before rendering so that all component errors and
// unhandled promise rejections are captured from the very first paint.
// When VITE_SENTRY_DSN is absent (local development without a Sentry project),
// init() is a no-op — no network calls are made. DSN is never hardcoded.
const sentryDsn = import.meta.env.VITE_SENTRY_DSN;

if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    // Maps to the Vite build mode ("development" | "production" | "staging").
    environment: import.meta.env.MODE,
    integrations: [
      // Instruments page navigation for performance tracing. Also captures
      // the current route in error events so stack traces include context.
      Sentry.browserTracingIntegration(),
    ],
    tracesSampleRate: 0.1,
    // PII guard: never send user email or display name automatically.
    // User context (only ID) is enriched after Clerk authentication.
    sendDefaultPii: false,
  });
}

const rootElement = document.getElementById('root');
if (!rootElement) {
  throw new Error('Root element #root not found in index.html');
}

createRoot(rootElement).render(
  <StrictMode>
    {/*
      ErrorBoundary catches uncaught React render errors and reports them to
      Sentry. The fallback is intentionally generic — no internal details
      or Sentry event IDs are shown to the user.
    */}
    <Sentry.ErrorBoundary
      fallback={<p>An unexpected error occurred. Our team has been notified.</p>}
    >
      <I18nextProvider i18n={i18n}>
        <App />
      </I18nextProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
);
