/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Sentry DSN injected at build time. Absent in local development — Sentry is a no-op when unset. */
  readonly VITE_SENTRY_DSN?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
