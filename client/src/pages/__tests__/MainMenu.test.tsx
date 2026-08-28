import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MainMenu } from '../MainMenu';

// Mock react-router-dom navigation
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock react-i18next — return key as value for predictable assertions
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

// Mock @clerk/clerk-react
const mockSignOut = vi.fn();
vi.mock('@clerk/clerk-react', () => ({
  useClerk: () => ({ signOut: mockSignOut }),
}));

describe('MainMenu', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
    mockSignOut.mockClear();
  });

  it('renders the main menu title', () => {
    render(<MainMenu />);
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
  });

  it('renders all three navigation buttons', () => {
    render(<MainMenu />);
    expect(
      screen.getByRole('button', { name: 'main_menu.play' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'main_menu.rules' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'main_menu.sign_out' }),
    ).toBeInTheDocument();
  });

  it('navigates to /lobby when Play is clicked', async () => {
    const user = userEvent.setup();
    render(<MainMenu />);

    await user.click(screen.getByRole('button', { name: 'main_menu.play' }));

    expect(mockNavigate).toHaveBeenCalledWith('/lobby');
  });

  it('navigates to /rules when Rules is clicked', async () => {
    const user = userEvent.setup();
    render(<MainMenu />);

    await user.click(screen.getByRole('button', { name: 'main_menu.rules' }));

    expect(mockNavigate).toHaveBeenCalledWith('/rules');
  });

  it('calls signOut when Sign Out is clicked', async () => {
    const user = userEvent.setup();
    render(<MainMenu />);

    await user.click(
      screen.getByRole('button', { name: 'main_menu.sign_out' }),
    );

    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });
});
