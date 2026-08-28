import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright E2E configuration.
 *
 * Base URL defaults to the local dev server; override with E2E_BASE_URL in CI
 * so tests point at the staging environment after deployment.
 *
 * Screenshots are captured automatically on test failure and are uploaded as CI
 * artifacts — see .github/workflows/deploy.yml.
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  // Fail the build if any test.only was accidentally committed.
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
  ],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    // Capture screenshots automatically on failure for CI artifact upload.
    screenshot: 'only-on-failure',
    // Record traces on retry to simplify debugging.
    trace: 'on-first-retry',
    // Global timeout per action (click, fill, etc.).
    actionTimeout: 10_000,
    // Clerk testing token — injected by CI from secrets, skipped locally
    // unless the developer sets the env var.
    extraHTTPHeaders: process.env.CLERK_TESTING_TOKEN
      ? { Authorization: `Bearer ${process.env.CLERK_TESTING_TOKEN}` }
      : {},
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  // Screenshot output directory (used by the CI artifact upload step).
  outputDir: 'test-results',
  timeout: 60_000,
});
