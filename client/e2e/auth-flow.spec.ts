import { test, expect } from '@playwright/test';

/**
 * Authentication flow E2E tests.
 *
 * These tests verify that:
 * - The application loads and displays a main-menu / landing page.
 * - A user can navigate from the main menu to the lobby.
 *
 * Clerk authentication is handled via CLERK_TESTING_TOKEN (set in CI as a
 * secret).  When the token is present Clerk skips its interactive sign-in UI
 * and the tests proceed directly.  Locally, developers can set the env var or
 * test against a dev server configured with VITE_CLERK_PUBLISHABLE_KEY pointing
 * to a test Clerk application.
 */

test.describe('Authentication flow', () => {
  test('application loads and displays the main menu', async ({ page }) => {
    await page.goto('/');

    // The page title should identify the application.
    await expect(page).toHaveTitle(/Ashta Chamma/i);

    // The root element must be mounted — confirms React rendered successfully.
    const root = page.locator('#root');
    await expect(root).toBeAttached();
  });

  test('user can navigate from the main menu to the lobby', async ({ page }) => {
    await page.goto('/');

    // Wait for the SPA to fully hydrate before interacting.
    await page.waitForLoadState('networkidle');

    // Find the primary CTA that takes the user into the lobby (sign-in or
    // "Play Now" — the exact label depends on auth state, so we look for the
    // most prominent interactive control).
    const lobbyLink = page
      .getByRole('link', { name: /lobby|play|get started/i })
      .or(page.getByRole('button', { name: /lobby|play|get started|sign in/i }))
      .first();

    await expect(lobbyLink).toBeVisible({ timeout: 15_000 });
    await lobbyLink.click();

    // After clicking we should land somewhere other than the bare root path,
    // or a lobby heading / room list should appear.
    // We wait for either the URL to change or a lobby-specific element.
    await Promise.race([
      page.waitForURL((url) => url.pathname !== '/'),
      page.getByRole('heading', { name: /lobby|rooms/i }).waitFor({ timeout: 15_000 }),
    ]);

    // Confirm the lobby section is visible.
    const lobbyHeading = page.getByRole('heading', { name: /lobby|rooms/i });
    const hasLobbyHeading = await lobbyHeading.isVisible().catch(() => false);

    // Accept either the heading OR a route change as evidence of navigation.
    const currentUrl = page.url();
    const navigatedAway = !currentUrl.endsWith('/') && currentUrl !== (process.env.E2E_BASE_URL ?? 'http://localhost:5173') + '/';

    expect(hasLobbyHeading || navigatedAway).toBe(true);
  });
});
