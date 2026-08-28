/**
 * Global test setup for Vitest.
 * Runs before each test file in the suite.
 */

// Reset the i18n language to English before each test to prevent
// state leakage between tests that call i18n.changeLanguage()
import i18n from './i18n/config';
import { beforeEach } from 'vitest';

beforeEach(async () => {
  await i18n.changeLanguage('en');
});
