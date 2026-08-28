import { describe, it, expect } from 'vitest';
import en from '../locales/en.json';
import te from '../locales/te.json';

/**
 * Recursively extracts all dot-separated leaf keys from a nested object.
 * e.g. { menu: { play: "Play" } } → ["menu.play"]
 */
function flattenKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  return Object.keys(obj).flatMap((key) => {
    const fullKey = prefix ? `${prefix}.${key}` : key;
    const value = obj[key];
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      return flattenKeys(value as Record<string, unknown>, fullKey);
    }
    return [fullKey];
  });
}

describe('Translation key parity', () => {
  it('te.json contains all keys present in en.json', () => {
    const enKeys = flattenKeys(en as Record<string, unknown>).sort();
    const teKeys = flattenKeys(te as Record<string, unknown>).sort();
    expect(teKeys).toEqual(enKeys);
  });

  it('en.json contains all keys present in te.json', () => {
    // Guard against te.json accidentally introducing extra keys
    const enKeys = flattenKeys(en as Record<string, unknown>).sort();
    const teKeys = flattenKeys(te as Record<string, unknown>).sort();
    expect(enKeys).toEqual(teKeys);
  });

  it('en.json has all required top-level namespaces', () => {
    const topLevel = Object.keys(en);
    expect(topLevel).toContain('menu');
    expect(topLevel).toContain('lobby');
    expect(topLevel).toContain('game');
    expect(topLevel).toContain('rules');
    expect(topLevel).toContain('errors');
    expect(topLevel).toContain('common');
    expect(topLevel).toContain('leaderboard');
  });

  it('en.json menu namespace has all required keys', () => {
    const { menu } = en;
    expect(menu).toHaveProperty('play');
    expect(menu).toHaveProperty('rules');
    expect(menu).toHaveProperty('signOut');
    expect(menu).toHaveProperty('title');
    expect(menu).toHaveProperty('welcome');
  });

  it('en.json errors namespace has all required keys', () => {
    const { errors } = en;
    expect(errors).toHaveProperty('roomFull');
    expect(errors).toHaveProperty('invalidCode');
    expect(errors).toHaveProperty('notYourTurn');
    expect(errors).toHaveProperty('invalidMove');
  });

  it('no translation value is an empty string', () => {
    const checkNoEmpty = (obj: Record<string, unknown>, path: string): void => {
      for (const [key, value] of Object.entries(obj)) {
        const currentPath = path ? `${path}.${key}` : key;
        if (typeof value === 'string') {
          expect(value, `Key "${currentPath}" must not be empty`).not.toBe('');
        } else if (typeof value === 'object' && value !== null) {
          checkNoEmpty(value as Record<string, unknown>, currentPath);
        }
      }
    };
    checkNoEmpty(en as Record<string, unknown>, 'en');
    checkNoEmpty(te as Record<string, unknown>, 'te');
  });
});
