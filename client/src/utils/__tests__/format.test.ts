import { describe, it, expect } from 'vitest';
import { formatNumber, formatDate, formatDateTime } from '../format';

describe('formatNumber', () => {
  it('returns a string', () => {
    expect(typeof formatNumber(42, 'en')).toBe('string');
  });

  it('formats a whole number in English locale with thousands separator', () => {
    // Intl.NumberFormat uses a comma separator for en
    expect(formatNumber(1000, 'en')).toBe('1,000');
  });

  it('formats zero', () => {
    expect(formatNumber(0, 'en')).toBe('0');
  });

  it('formats negative numbers', () => {
    const result = formatNumber(-500, 'en');
    expect(result).toContain('500');
  });

  it('formats decimal numbers in English locale', () => {
    const result = formatNumber(1234.56, 'en');
    expect(result).toContain('1,234');
  });

  it('formats a number in Telugu locale without throwing', () => {
    expect(() => formatNumber(1000, 'te')).not.toThrow();
    const result = formatNumber(1000, 'te');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });

  it('handles large numbers', () => {
    const result = formatNumber(1_000_000, 'en');
    expect(result).toContain('1,000,000');
  });
});

describe('formatDate', () => {
  // Use a fixed date to avoid timezone-dependent failures
  const fixedDate = new Date(2024, 0, 15); // 15 Jan 2024

  it('returns a string', () => {
    expect(typeof formatDate(fixedDate, 'en')).toBe('string');
  });

  it('includes the year in English locale output', () => {
    const result = formatDate(fixedDate, 'en');
    expect(result).toContain('2024');
  });

  it('includes the day number in English locale output', () => {
    const result = formatDate(fixedDate, 'en');
    expect(result).toContain('15');
  });

  it('formats a date in Telugu locale without throwing', () => {
    expect(() => formatDate(fixedDate, 'te')).not.toThrow();
    const result = formatDate(fixedDate, 'te');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });
});

describe('formatDateTime', () => {
  const fixedDate = new Date(2024, 0, 15, 10, 30); // 15 Jan 2024 10:30

  it('returns a string', () => {
    expect(typeof formatDateTime(fixedDate, 'en')).toBe('string');
  });

  it('includes the year in the formatted output', () => {
    const result = formatDateTime(fixedDate, 'en');
    expect(result).toContain('2024');
  });

  it('formats in Telugu locale without throwing', () => {
    expect(() => formatDateTime(fixedDate, 'te')).not.toThrow();
    const result = formatDateTime(fixedDate, 'te');
    expect(result.length).toBeGreaterThan(0);
  });
});
