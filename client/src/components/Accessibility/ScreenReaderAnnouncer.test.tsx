import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { ScreenReaderAnnouncer } from './ScreenReaderAnnouncer';

describe('ScreenReaderAnnouncer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a visually hidden live region with role="status"', () => {
    render(<ScreenReaderAnnouncer message="" />);
    const region = screen.getByRole('status');
    expect(region).toBeInTheDocument();
  });

  it('uses aria-live="polite" by default', () => {
    render(<ScreenReaderAnnouncer message="test" />);
    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-live', 'polite');
  });

  it('uses aria-live="assertive" when priority is set to assertive', () => {
    render(<ScreenReaderAnnouncer message="urgent" priority="assertive" />);
    const region = document.querySelector('[aria-live="assertive"]');
    expect(region).toBeInTheDocument();
  });

  it('sets aria-atomic="true" so the entire announcement is read', () => {
    render(<ScreenReaderAnnouncer message="test" />);
    const region = screen.getByRole('status');
    expect(region).toHaveAttribute('aria-atomic', 'true');
  });

  it('populates the live region with the message after 50 ms debounce', async () => {
    render(<ScreenReaderAnnouncer message="Rolled 4" />);
    const region = screen.getByRole('status');
    // Before the debounce fires the element is empty.
    expect(region.textContent).toBe('');

    await act(async () => {
      vi.advanceTimersByTime(50);
    });

    expect(region.textContent).toBe('Rolled 4');
  });

  it('clears then re-sets text so identical repeat messages are announced', async () => {
    const { rerender } = render(<ScreenReaderAnnouncer message="Rolled 2" />);

    await act(async () => {
      vi.advanceTimersByTime(50);
    });

    const region = screen.getByRole('status');
    expect(region.textContent).toBe('Rolled 2');

    // Re-render with the same message — the clear+set cycle must still fire.
    rerender(<ScreenReaderAnnouncer message="Rolled 2" />);
    expect(region.textContent).toBe('');

    await act(async () => {
      vi.advanceTimersByTime(50);
    });

    expect(region.textContent).toBe('Rolled 2');
  });

  it('has visually hidden styles (sr-only pattern)', () => {
    render(<ScreenReaderAnnouncer message="hidden" />);
    const region = screen.getByRole('status');
    expect(region).toHaveStyle({ position: 'absolute' });
    expect(region).toHaveStyle({ width: '1px' });
    expect(region).toHaveStyle({ height: '1px' });
    expect(region).toHaveStyle({ overflow: 'hidden' });
  });
});
