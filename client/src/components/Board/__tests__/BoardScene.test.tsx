import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';

// Mock @react-three/fiber Canvas so tests run in jsdom without a WebGL context.
vi.mock('@react-three/fiber', () => ({
  Canvas: ({ children }: { children: ReactNode }) => (
    <div data-testid="r3f-canvas">{children}</div>
  ),
}));

// Mock @react-three/drei so OrbitControls renders as null in tests.
vi.mock('@react-three/drei', () => ({
  OrbitControls: () => null,
}));

// Mock Board3D to isolate the scene wrapper under test.
vi.mock('../Board3D', () => ({
  Board3D: () => <div data-testid="board-3d" />,
}));

// Imports after vi.mock — Vitest hoists mock calls automatically.
import { BoardScene } from '../BoardScene';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('BoardScene', () => {
  it('renders the full-viewport container', () => {
    render(<BoardScene />);
    const container = screen.getByTestId('board-scene-container');
    expect(container).toBeInTheDocument();
  });

  it('mounts the R3F Canvas', () => {
    render(<BoardScene />);
    expect(screen.getByTestId('r3f-canvas')).toBeInTheDocument();
  });

  it('renders the Board3D inside the Canvas', () => {
    render(<BoardScene />);
    expect(screen.getByTestId('board-3d')).toBeInTheDocument();
  });

  it('is accessible at /game route when embedded in a router', () => {
    render(
      <MemoryRouter initialEntries={['/game']}>
        <BoardScene />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('board-scene-container')).toBeInTheDocument();
  });
});
