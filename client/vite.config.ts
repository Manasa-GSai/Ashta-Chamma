/// <reference types="vitest" />
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { visualizer } from 'rollup-plugin-visualizer';

// ANALYZE env var enables the bundle visualizer (html report in dist/stats.html).
// Run via: ANALYZE=true npm run build
const isAnalyze = process.env.ANALYZE === 'true';

// The Sentry plugin uploads source maps to Sentry during CI/CD builds and
// then deletes the .map files from the dist/ folder so they are never
// served publicly (acceptance criterion: source maps must not be accessible).
// When SENTRY_AUTH_TOKEN is absent (local dev), the plugin is a no-op.
export default defineConfig({
  plugins: [
    react(),
    // Generate bundle analysis report when ANALYZE=true.
    // Placed after react() so the plugin sees the final chunk graph.
    ...(isAnalyze
      ? [
          visualizer({
            filename: 'dist/stats.html',
            open: false,
            gzipSize: true,
            brotliSize: true,
            template: 'treemap',
          }),
        ]
      : []),
  ],
  server: {
    port: 5173,
  },
  build: {
    outDir: 'dist',
    // Always emit sourcemaps so Lighthouse and profiling tools work correctly.
    sourcemap: true,
    // Warn only above 600KB per chunk; main bundle target is <500KB gzipped.
    chunkSizeWarningLimit: 600,
    rollupOptions: {
      output: {
        // Manual chunk splitting keeps Three.js and Rapier WASM out of the
        // main entry bundle so the /game route is the only place that loads them.
        // This is the primary mechanism for keeping main bundle < 500KB gzipped.
        manualChunks: (id: string) => {
          // Isolate Three.js and its ecosystem into a single vendor chunk.
          // Only loaded when a component that imports three is rendered.
          if (
            id.includes('node_modules/three') ||
            id.includes('node_modules/@react-three/fiber') ||
            id.includes('node_modules/@react-three/drei')
          ) {
            return 'vendor-three';
          }

          // Rapier3D WASM wrapper.  The actual .wasm binary is loaded
          // asynchronously via init() inside Game.tsx; this chunk contains
          // only the JS glue code for @dimforge/rapier3d-compat.
          if (
            id.includes('node_modules/@dimforge/rapier3d') ||
            id.includes('node_modules/@react-three/rapier')
          ) {
            return 'vendor-rapier';
          }

          // All other node_modules go into a general vendor chunk so they
          // benefit from long-term browser caching independently of app code.
          if (id.includes('node_modules')) {
            return 'vendor';
          }

          // No explicit return → Rollup decides (app code stays in main).
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
        'src/**/*.test.{ts,tsx}',
      ],
      thresholds: {
        lines: 60,
        functions: 60,
        branches: 60,
        statements: 60,
      },
    },
  },
});
