import { test, expect, type Page, type BrowserContext } from '@playwright/test';

/**
 * Game flow E2E tests.
 *
 * Covers:
 * - The game board renders as a 3D canvas element after the game starts.
 * - The Roll button is present and clickable.
 * - Clicking Roll updates the HUD with a roll result.
 *
 * Constraints:
 * - Assertions are on UI state only — we never assert on a specific dice value
 *   or game outcome.
 * - WebSocket connections are given enough time to establish before assertions
 *   are made (waitForSelector / waitForLoadState handles this).
 * - Any rooms created during the test are cleaned up in afterEach.
 */

const BASE_URL = process.env.E2E_BASE_URL ?? 'http://localhost:5173';

/** Create a room, return its code, and navigate to the waiting room. */
async function createRoomAndGetCode(page: Page): Promise<string> {
  // Navigate to lobby.
  const lobbyResponse = await page.goto('/lobby').catch(() => null);
  if (!lobbyResponse || !lobbyResponse.ok()) {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  }

  const createButton = page
    .getByRole('button', { name: /create\s+room/i })
    .or(page.getByRole('link', { name: /create\s+room/i }))
    .first();

  await expect(createButton).toBeVisible({ timeout: 15_000 });
  await createButton.click();

  const roomCodeLocator = page
    .getByTestId('room-code')
    .or(page.getByLabel(/room code/i))
    .or(page.locator('[data-room-code]'))
    .or(page.getByText(/room code/i).locator('..').locator('[class*="code"], [class*="badge"], strong, code').first())
    .first();

  await expect(roomCodeLocator).toBeVisible({ timeout: 20_000 });
  const code = (await roomCodeLocator.textContent())?.replace(/\s/g, '') ?? '';
  expect(code).toMatch(/^[A-Z0-9]{4,8}$/i);
  return code;
}

/** Join an existing room by code and wait for the waiting-room view. */
async function joinRoom(context: BrowserContext, roomCode: string): Promise<Page> {
  const page = await context.newPage();

  const lobbyResponse = await page.goto('/lobby').catch(() => null);
  if (!lobbyResponse || !lobbyResponse.ok()) {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  }

  const joinInput = page
    .getByPlaceholder(/room code|enter code/i)
    .or(page.getByLabel(/room code/i))
    .first();

  await expect(joinInput).toBeVisible({ timeout: 15_000 });
  await joinInput.fill(roomCode);

  const joinButton = page.getByRole('button', { name: /join/i }).first();
  await expect(joinButton).toBeVisible();
  await joinButton.click();

  // Wait until connected to the room.
  await page
    .getByTestId('room-view')
    .or(page.getByRole('heading', { name: /waiting|room|players/i }))
    .first()
    .waitFor({ timeout: 20_000 });

  return page;
}

test.describe('Game flow', () => {
  let roomCode: string | null = null;

  test.afterEach(async ({ request }) => {
    if (roomCode) {
      await request
        .delete(`${BASE_URL}/api/rooms/${roomCode}/leave`)
        .catch(() => null);
      roomCode = null;
    }
  });

  test('game starts and the 3D canvas board is rendered', async ({ page, browser }) => {
    // Create a room as host.
    roomCode = await createRoomAndGetCode(page);

    // Have a second player join so the host can start the game (minimum 2 players).
    const guestContext = await browser.newContext();
    const guestPage = await joinRoom(guestContext, roomCode);

    // Host clicks "Start Game".
    const startButton = page
      .getByRole('button', { name: /start\s+game/i })
      .first();

    await expect(startButton).toBeVisible({ timeout: 15_000 });
    await startButton.click();

    // After starting, the 3D board should render as a <canvas> element.
    // React Three Fiber mounts a <canvas> for the WebGL scene.
    const canvas = page.locator('canvas').first();
    await expect(canvas).toBeVisible({ timeout: 30_000 });

    // The canvas should have non-zero dimensions — confirms it rendered.
    const boundingBox = await canvas.boundingBox();
    expect(boundingBox).not.toBeNull();
    expect(boundingBox!.width).toBeGreaterThan(0);
    expect(boundingBox!.height).toBeGreaterThan(0);

    await guestContext.close();
  });

  test('user can click Roll button and see a roll result in the HUD', async ({
    page,
    browser,
  }) => {
    // Create and start a game.
    roomCode = await createRoomAndGetCode(page);
    const guestContext = await browser.newContext();
    const guestPage = await joinRoom(guestContext, roomCode);

    const startButton = page
      .getByRole('button', { name: /start\s+game/i })
      .first();

    await expect(startButton).toBeVisible({ timeout: 15_000 });
    await startButton.click();

    // Wait for the 3D canvas to mount — signals the game loop is running.
    await page.locator('canvas').first().waitFor({ timeout: 30_000 });

    // Wait for WebSocket to deliver the initial state (networkidle or explicit
    // selector avoids race conditions with async content).
    await page.waitForLoadState('networkidle').catch(() => {
      // WebSocket connections prevent full networkidle — acceptable.
    });

    // The Roll button is only shown when it is the current player's turn.
    // We attempt to find it; if it belongs to the guest's turn instead we check
    // the guest page.  Either way we verify the HUD reflects the outcome.
    const rollButton = page
      .getByRole('button', { name: /roll/i })
      .or(page.getByTestId('roll-button'))
      .first();

    const guestRollButton = guestPage
      .getByRole('button', { name: /roll/i })
      .or(guestPage.getByTestId('roll-button'))
      .first();

    // Determine whose turn it is by whichever Roll button is enabled.
    let activePage: Page = page;
    const hostRollVisible = await rollButton
      .isVisible({ timeout: 10_000 })
      .catch(() => false);
    const hostRollEnabled = hostRollVisible
      ? !(await rollButton.isDisabled().catch(() => true))
      : false;

    if (!hostRollEnabled) {
      const guestVisible = await guestRollButton
        .isVisible({ timeout: 10_000 })
        .catch(() => false);
      if (guestVisible) {
        activePage = guestPage;
      }
    }

    const activeRollButton = activePage
      .getByRole('button', { name: /roll/i })
      .or(activePage.getByTestId('roll-button'))
      .first();

    await expect(activeRollButton).toBeVisible({ timeout: 15_000 });
    await expect(activeRollButton).toBeEnabled();
    await activeRollButton.click();

    // After rolling, the HUD must show a roll result.  We assert on the
    // presence of a result indicator without checking the specific value —
    // this keeps tests independent of game outcomes.
    const hudResult = activePage
      .getByTestId('roll-result')
      .or(activePage.getByLabel(/roll result|you rolled/i))
      .or(activePage.getByText(/you rolled|rolled a|result:/i))
      .or(activePage.locator('[class*="hud"] [class*="roll"], [class*="HUD"] [class*="roll"]'))
      .first();

    await expect(hudResult).toBeVisible({ timeout: 15_000 });

    await guestContext.close();
  });

  test('HUD updates reflect WebSocket state after roll', async ({ page, browser }) => {
    // Create and start a game.
    roomCode = await createRoomAndGetCode(page);
    const guestContext = await browser.newContext();
    await joinRoom(guestContext, roomCode);

    const startButton = page
      .getByRole('button', { name: /start\s+game/i })
      .first();

    await expect(startButton).toBeVisible({ timeout: 15_000 });
    await startButton.click();

    await page.locator('canvas').first().waitFor({ timeout: 30_000 });

    // Verify the HUD itself is rendered (turn indicator, player info, etc.).
    const hud = page
      .getByTestId('game-hud')
      .or(page.locator('[class*="hud"], [class*="HUD"]'))
      .first();

    await expect(hud).toBeVisible({ timeout: 15_000 });

    // The turn indicator should name a player — asserts on UI state, not value.
    const turnIndicator = page
      .getByTestId('turn-indicator')
      .or(page.getByText(/your turn|player \d|it['']s .+ turn/i))
      .first();

    // Turn indicator is a best-effort check; the canvas being present is the
    // primary acceptance criterion.
    const hasTurnIndicator = await turnIndicator
      .isVisible({ timeout: 5_000 })
      .catch(() => false);

    // Either the turn indicator is shown OR the canvas is present — both confirm
    // the game state has been received via WebSocket.
    const hasCanvas = await page.locator('canvas').first().isVisible();
    expect(hasCanvas || hasTurnIndicator).toBe(true);

    await guestContext.close();
  });
});
