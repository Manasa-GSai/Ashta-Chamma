/**
 * @vitest-environment jsdom
 *
 * Tests for MainMenu.tsx — the landing page that must load without any 3D
 * dependencies and achieve Lighthouse performance score ≥ 85.
 *
 * Strategy:
 *   - Verify the page renders key navigation elements.
 *   - Verify that Three.js / Rapier are NOT imported by this module (import
 *     boundary test) — done by checking the mock registry does not show those
 *     modules being called when MainMenu renders.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import MainMenu from '../pages/MainMenu';

// Guard that 3D modules are not loaded when MainMenu renders.
vi.mock('three', () => {
  throw new Error('Three.js must not be imported by MainMenu');
});

vi.mock('@dimforge/rapier3d-compat', () => {
  throw new Error('Rapier must not be imported by MainMenu');
});

describe('MainMenu page', () => {
  it('renders the game title', () => {
    render(
      <MemoryRouter>
        <MainMenu />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: /ashta chamma 3d/i })).toBeInTheDocument();
  });

  it('renders a Play link to /game', () => {
    render(
      <MemoryRouter>
        <MainMenu />
      </MemoryRouter>,
    );

    const playLink = screen.getByRole('link', { name: /play/i });
    expect(playLink).toBeInTheDocument();
    expect(playLink).toHaveAttribute('href', '/game');
  });

  it('renders a Leaderboard link', () => {
    render(
      <MemoryRouter>
        <MainMenu />
      </MemoryRouter>,
    );

    const lbLink = screen.getByRole('link', { name: /leaderboard/i });
    expect(lbLink).toBeInTheDocument();
    expect(lbLink).toHaveAttribute('href', '/leaderboard');
  });
});
