import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import * as apiModule from '../lib/api';
import { Leaderboard, type LeaderboardEntry } from './Leaderboard';

// Shared mock data
const mockEntries: LeaderboardEntry[] = [
  { rank: 1, user_id: 'user-1', display_name: 'Alice', total_wins: 42, total_games: 50 },
  { rank: 2, user_id: 'user-2', display_name: 'Bob', total_wins: 30, total_games: 45 },
  { rank: 3, user_id: 'user-3', display_name: 'Carol', total_wins: 20, total_games: 40 },
];

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('Leaderboard', () => {
  it('renders the leaderboard table with mock data', async () => {
    vi.spyOn(apiModule, 'apiFetch').mockResolvedValueOnce(mockEntries);

    render(<Leaderboard />);

    // Loading state is shown first
    expect(screen.getByRole('status')).toHaveTextContent('Loading');

    // Wait for data to appear
    await waitFor(() => {
      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Bob')).toBeInTheDocument();
    expect(screen.getByText('Carol')).toBeInTheDocument();

    // Rank column
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.getByText('2')).toBeInTheDocument();

    // Win rate for Alice: 42/50 = 84%
    expect(screen.getByText('84%')).toBeInTheDocument();
  });

  it('highlights the current user row with "(You)" badge', async () => {
    vi.spyOn(apiModule, 'apiFetch').mockResolvedValueOnce(mockEntries);

    render(<Leaderboard currentUserId="user-2" />);

    await waitFor(() => {
      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    // Bob (user-2) should have "(You)" badge
    expect(screen.getByText('(You)')).toBeInTheDocument();

    // Row for Bob should have aria-current set
    const rows = screen.getAllByRole('row');
    // First row is the header, Bob is 2nd data row → rows[2]
    expect(rows[2]).toHaveAttribute('aria-current', 'true');
  });

  it('does not show "(You)" badge when currentUserId is not in entries', async () => {
    vi.spyOn(apiModule, 'apiFetch').mockResolvedValueOnce(mockEntries);

    render(<Leaderboard currentUserId="user-99" />);

    await waitFor(() => {
      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    expect(screen.queryByText('(You)')).not.toBeInTheDocument();
  });

  it('changes the API query parameter when a period filter is clicked', async () => {
    const spy = vi
      .spyOn(apiModule, 'apiFetch')
      .mockResolvedValue(mockEntries);

    render(<Leaderboard />);

    // Initial fetch uses default period "all"
    await waitFor(() => {
      expect(screen.getByRole('table')).toBeInTheDocument();
    });
    expect(spy).toHaveBeenLastCalledWith(
      expect.stringContaining('period=all'),
    );

    // Click the "Week" filter
    fireEvent.click(screen.getByRole('button', { name: 'Week' }));

    await waitFor(() => {
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining('period=week'),
      );
    });

    // Click the "Month" filter
    fireEvent.click(screen.getByRole('button', { name: 'Month' }));

    await waitFor(() => {
      expect(spy).toHaveBeenLastCalledWith(
        expect.stringContaining('period=month'),
      );
    });
  });

  it('shows loading state while fetching', async () => {
    // Never resolves so loading stays visible
    vi.spyOn(apiModule, 'apiFetch').mockReturnValue(new Promise(() => undefined));

    render(<Leaderboard />);

    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });

  it('shows an error state with a retry button when the API fails', async () => {
    vi.spyOn(apiModule, 'apiFetch').mockRejectedValueOnce(
      new apiModule.ApiError('Server error', 500),
    );

    render(<Leaderboard />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    expect(screen.getByRole('alert')).toHaveTextContent('Server error');
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
  });

  it('retries the API call when the retry button is clicked', async () => {
    const spy = vi
      .spyOn(apiModule, 'apiFetch')
      .mockRejectedValueOnce(new apiModule.ApiError('Server error', 500))
      .mockResolvedValueOnce(mockEntries);

    render(<Leaderboard />);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    await waitFor(() => {
      expect(screen.getByRole('table')).toBeInTheDocument();
    });

    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('shows an empty message when the API returns no entries', async () => {
    vi.spyOn(apiModule, 'apiFetch').mockResolvedValueOnce([]);

    render(<Leaderboard />);

    await waitFor(() => {
      expect(screen.getByText(/No scores yet/i)).toBeInTheDocument();
    });

    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});
