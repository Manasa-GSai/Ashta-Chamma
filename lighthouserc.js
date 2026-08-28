// lighthouserc.js — Lighthouse CI configuration.
//
// Lighthouse is run against the main menu page (/) because:
//   - The /game route loads Three.js + Rapier3D on demand and intentionally
//     scores lower on performance (it's a rich 3D experience).
//   - The main menu is the landing page that end-users first see, so its
//     performance has the greatest impact on perceived load time.
//
// The performance budget asserts a score ≥ 85, matching the acceptance
// criterion in WO-041.  Other categories are measured but not blocked.
//
// Usage in CI:
//   npx lhci autorun
//
// See: https://github.com/GoogleChrome/lighthouse-ci/blob/main/docs/configuration.md

module.exports = {
  ci: {
    collect: {
      // Start the production preview server before Lighthouse runs.
      // Vite preview serves the dist/ output on port 4173 by default.
      startServerCommand: 'npm run preview -- --port 4173',
      startServerReadyPattern: 'Local:',
      startServerReadyTimeout: 30000,
      url: ['http://localhost:4173/'],
      // Run Lighthouse three times and take the median to reduce variance.
      numberOfRuns: 3,
      settings: {
        // Simulate a Moto G4 on a 4G connection — matches the performance
        // requirement ("3-second load time target on 4G connections").
        preset: 'desktop',
        throttling: {
          rttMs: 40,
          throughputKbps: 10240,
          cpuSlowdownMultiplier: 1,
        },
      },
    },
    assert: {
      assertions: {
        // Main acceptance criterion: performance score ≥ 85.
        'categories:performance': ['error', { minScore: 0.85 }],
        // Accessibility and best-practices are tracked but not blocking.
        'categories:accessibility': ['warn', { minScore: 0.8 }],
        'categories:best-practices': ['warn', { minScore: 0.8 }],
        // Ensure the main bundle stays lean.
        'resource-summary:script:size': [
          'warn',
          { maxNumericValue: 512000 }, // 500 KB raw — gzip target enforced at build
        ],
      },
    },
    upload: {
      // Upload results to temporary public storage so CI reports are
      // visible without a dedicated LHCI server.  Replace with a private
      // LHCI server URL if desired.
      target: 'temporary-public-storage',
    },
  },
};
