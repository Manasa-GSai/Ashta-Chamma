/**
 * @vitest-environment jsdom
 *
 * Tests for Game.tsx — the 3D game route with async Rapier3D initialisation.
 *
 * Strategy:
 *   - Mock @dimforge/rapier3d-compat so tests do not depend on a real WASM
 *     binary being present in the test environment.
 *   - Verify the loading state is shown before physics are ready.
 *   - Verify the game canvas is shown after physics init completes.
 *   - Verify errors during physics init are handled gracefully (no crash).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Mock Rapier3D — the real module requires a .wasm binary which is not
// available in jsdom.  We replace it with a synchronously-resolving stub.
// ---------------------------------------------------------------------------

const mockRapierInit = vi.fn().mockResolvedValue(undefined);

vi.mock('@dimforge/rapier3d-compat', () => ({
  init: mockRapierInit,
}));

// ---------------------------------------------------------------------------
// Import the component under test AFTER the mock is registered.
// ---------------------------------------------------------------------------

import Game from '../pages/Game';

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('Game page', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRapierInit.mockResolvedValue(undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows an "Initialising physics" message while Rapier is loading', () => {
    // Make init() never resolve so we stay in the loading state.
    mockRapierInit.mockReturnValue(new Promise(() => {}));

    render(<Game />);

    expect(screen.getByText(/initialising physics/i)).toBeInTheDocument();
  });

  it('shows the game canvas after Rapier initialises successfully', async () => {
    await act(async () => {
      render(<Game />);
    });

    // After init() resolves the loading state should be replaced by the canvas.
    await waitFor(() => {
      expect(screen.getByLabelText(/3D game board/i)).toBeInTheDocument();
    });
  });

  it('does not crash when Rapier init throws an error', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockRapierInit.mockRejectedValue(new Error('WASM load failed'));

    // Should render without throwing.
    await act(async () => {
      render(<Game />);
    });

    // Error is logged to console (not swallowed silently without reason).
    await waitFor(() => {
      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('[Game] Failed to initialise Rapier3D WASM:'),
        expect.any(Error),
      );
    });

    consoleSpy.mockRestore();
  });
});
