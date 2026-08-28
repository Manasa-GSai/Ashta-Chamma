import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { sentryVitePlugin } from '@sentry/vite-plugin';

// The Sentry plugin uploads source maps to Sentry during CI/CD builds and
// then deletes the .map files from the dist/ folder so they are never
// served publicly (acceptance criterion: source maps must not be accessible).
// When SENTRY_AUTH_TOKEN is absent (local dev), the plugin is a no-op.
export default defineConfig({
  plugins: [
    react(),
    sentryVitePlugin({
      org: process.env.SENTRY_ORG,
      project: process.env.SENTRY_PROJECT,
      authToken: process.env.SENTRY_AUTH_TOKEN,
      sourcemaps: {
        // Remove map files from the build output after upload so they are
        // never deployed to the public CDN (S3/CloudFront).
        filesToDeleteAfterUpload: process.env.CI ? ['./dist/**/*.map'] : [],
      },
      // Silence the plugin in local dev to avoid noisy console warnings.
      silent: !process.env.CI,
    }),
  ],
  server: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    // Source maps are required so Sentry can de-minify stack traces.
    sourcemap: true,
  },
});
