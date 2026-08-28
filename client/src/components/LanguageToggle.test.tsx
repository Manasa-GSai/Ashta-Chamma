import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

// Use vi.hoisted so that mockChangeLanguage is available inside the vi.mock factory,
// which is hoisted to the top of the file before any module-level variable initialisers.
const mockChangeLanguage = vi.hoisted(() => vi.fn().mockResolvedValue(undefined));

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    i18n: {
      language: 'en',
      changeLanguage: mockChangeLanguage,
    },
    t: (_key: string, fallback?: string) => fallback ?? _key,
  }),
}));

import { LanguageToggle } from './LanguageToggle';

describe('LanguageToggle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('rendering', () => {
    it('renders a language selector', () => {
      render(<LanguageToggle />);
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('renders the English option', () => {
      render(<LanguageToggle />);
      expect(screen.getByRole('option', { name: 'English' })).toBeInTheDocument();
    });

    it('renders the Telugu option', () => {
      render(<LanguageToggle />);
      expect(screen.getByRole('option', { name: 'తెలుగు' })).toBeInTheDocument();
    });

    it('renders the Hindi option', () => {
      render(<LanguageToggle />);
      expect(screen.getByRole('option', { name: 'हिंदी' })).toBeInTheDocument();
    });

    it('renders a label associated with the selector', () => {
      render(<LanguageToggle />);
      // The select is labelled via htmlFor="language-select"
      expect(screen.getByLabelText(/language/i)).toBeInTheDocument();
    });
  });

  describe('language switching', () => {
    it('calls changeLanguage with "te" when Telugu is selected', async () => {
      render(<LanguageToggle />);
      await userEvent.selectOptions(screen.getByRole('combobox'), 'te');
      expect(mockChangeLanguage).toHaveBeenCalledWith('te');
    });

    it('calls changeLanguage with "hi" when Hindi is selected', async () => {
      render(<LanguageToggle />);
      await userEvent.selectOptions(screen.getByRole('combobox'), 'hi');
      expect(mockChangeLanguage).toHaveBeenCalledWith('hi');
    });

    it('calls changeLanguage with "en" when English is selected', async () => {
      render(<LanguageToggle />);
      await userEvent.selectOptions(screen.getByRole('combobox'), 'en');
      expect(mockChangeLanguage).toHaveBeenCalledWith('en');
    });

    it('calls changeLanguage exactly once per selection', async () => {
      render(<LanguageToggle />);
      await userEvent.selectOptions(screen.getByRole('combobox'), 'te');
      expect(mockChangeLanguage).toHaveBeenCalledTimes(1);
    });
  });
});
