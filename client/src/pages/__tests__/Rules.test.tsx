import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Rules } from '../Rules';

// Mock react-router-dom
const mockNavigate = vi.fn();
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}));

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key: string) => key,
  }),
}));

describe('Rules', () => {
  beforeEach(() => {
    mockNavigate.mockClear();
  });

  it('renders the page title', () => {
    render(<Rules />);
    expect(
      screen.getByRole('heading', { name: 'rules.title', level: 1 }),
    ).toBeInTheDocument();
  });

  it('renders all rule sections', () => {
    render(<Rules />);

    expect(
      screen.getByRole('heading', { name: 'rules.objective_title' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'rules.cowrie_title' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'rules.roll_values_title' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'rules.movement_title' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { name: 'rules.safe_squares_title' }),
    ).toBeInTheDocument();
  });

  it('renders the Back button', () => {
    render(<Rules />);
    expect(
      screen.getByRole('button', { name: /rules\.back/i }),
    ).toBeInTheDocument();
  });

  it('navigates to / when Back is clicked', async () => {
    const user = userEvent.setup();
    render(<Rules />);

    await user.click(screen.getByRole('button', { name: /rules\.back/i }));

    expect(mockNavigate).toHaveBeenCalledWith('/');
  });

  it('renders roll value entries', () => {
    render(<Rules />);
    // Five roll values should appear as list items
    const rollItems = screen.getAllByRole('listitem');
    expect(rollItems.length).toBeGreaterThanOrEqual(5);
  });
});
