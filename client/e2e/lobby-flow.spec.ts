import { test, expect, type Page } from '@playwright/test';

/**
 * Lobby flow E2E tests.
 *
 * Covers:
 * - Creating a room and verifying the room code is shown.
 * - Joining an existing room with a valid code.
 *
 * Constraints:
 * - Tests must clean up any rooms they create (handled via the leave/delete API
 *   or by the server's idle-room TTL — the afterEach hook sends a leave request
 *   when a room code was obtained).
 * - Assertions are on UI state, not specific game outcomes.
 */

/** Navigate to the lobby, handling whatever auth state the dev server exposes. */
async function navigateToLobby(page: Page): Promise<void> {
  await page.goto('/');
  await page.waitForLoadState('networkidle');

  // If there is an explicit lobby route, use it.
  const response = await page.goto('/lobby').catch(() => null);
  if (response && response.ok()) {
    await page.waitForLoadState('networkidle');
    return;
  }

  // Otherwise find the navigation element from the main menu.
  await page.goto('/');
  const lobbyLink = page
    .getByRole('link', { name: /lobby/i })
    .or(page.getByRole('button', { name: /lobby|play/i }))
    .first();
  if (await lobbyLink.isVisible({ timeout: 5_000 }).catch(() => false)) {
    await lobbyLink.click();
    await page.waitForLoadState('networkidle');
  }
}

test.describe('Lobby flow', () => {
  let createdRoomCode: string | null = null;

  test.afterEach(async ({ request }) => {
    // Clean up: leave / delete the room so the test database stays tidy.
    if (createdRoomCode) {
      const baseUrl = process.env.E2E_BASE_URL ?? 'http://localhost:5173';
      // Best-effort — ignore failures (e.g. room already cleaned up by server TTL).
      await request
        .delete(`${baseUrl}/api/rooms/${createdRoomCode}/leave`)
        .catch(() => null);
      createdRoomCode = null;
    }
  });

  test('user can create a room and see the room code', async ({ page }) => {
    await navigateToLobby(page);

    // Find and click the "Create Room" button.
    const createButton = page
      .getByRole('button', { name: /create\s+room/i })
      .or(page.getByRole('link', { name: /create\s+room/i }))
      .first();

    await expect(createButton).toBeVisible({ timeout: 15_000 });
    await createButton.click();

    // Wait for the room-code element to appear.  The code is typically a
    // short alphanumeric string rendered in a prominent element.
    const roomCodeLocator = page
      .getByTestId('room-code')
      .or(page.getByLabel(/room code/i))
      .or(page.locator('[data-room-code]'))
      .or(page.getByText(/room code/i).locator('..').locator('[class*="code"], [class*="badge"], strong, code').first())
      .first();

    await expect(roomCodeLocator).toBeVisible({ timeout: 20_000 });

    const roomCode = await roomCodeLocator.textContent();
    expect(roomCode).toBeTruthy();
    // Room codes are typically 4–8 alphanumeric characters.
    expect(roomCode?.replace(/\s/g, '')).toMatch(/^[A-Z0-9]{4,8}$/i);

    createdRoomCode = roomCode?.replace(/\s/g, '') ?? null;
  });

  test('user can join a room with a valid code', async ({ page, browser }) => {
    // Step 1: Create a room in a first browser context (host).
    const hostContext = await browser.newContext();
    const hostPage = await hostContext.newPage();
    await navigateToLobby(hostPage);

    const createButton = hostPage
      .getByRole('button', { name: /create\s+room/i })
      .or(hostPage.getByRole('link', { name: /create\s+room/i }))
      .first();

    await expect(createButton).toBeVisible({ timeout: 15_000 });
    await createButton.click();

    const roomCodeLocator = hostPage
      .getByTestId('room-code')
      .or(hostPage.getByLabel(/room code/i))
      .or(hostPage.locator('[data-room-code]'))
      .or(hostPage.getByText(/room code/i).locator('..').locator('[class*="code"], [class*="badge"], strong, code').first())
      .first();

    await expect(roomCodeLocator).toBeVisible({ timeout: 20_000 });
    const roomCode = (await roomCodeLocator.textContent())?.replace(/\s/g, '') ?? '';
    expect(roomCode).toMatch(/^[A-Z0-9]{4,8}$/i);
    createdRoomCode = roomCode;

    // Step 2: Join the room from the main test page (guest).
    await navigateToLobby(page);

    const joinInput = page
      .getByPlaceholder(/room code|enter code/i)
      .or(page.getByLabel(/room code/i))
      .first();

    await expect(joinInput).toBeVisible({ timeout: 15_000 });
    await joinInput.fill(roomCode);

    const joinButton = page
      .getByRole('button', { name: /join/i })
      .first();

    await expect(joinButton).toBeVisible();
    await joinButton.click();

    // After joining, the user should land inside the room — look for a
    // waiting-room or game-lobby indicator.
    const roomView = page
      .getByTestId('room-view')
      .or(page.getByRole('heading', { name: /waiting|room|players/i }))
      .or(page.locator('[data-room-id]'))
      .first();

    await expect(roomView).toBeVisible({ timeout: 20_000 });

    await hostContext.close();
  });
});
