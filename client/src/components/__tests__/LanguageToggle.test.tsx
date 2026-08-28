import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../i18n/config';
import { LanguageToggle } from '../LanguageToggle';

afterEach(() => {
  cleanup();
});

const renderWithI18n = (lng = 'en') => {
  void i18n.changeLanguage(lng);
  return render(
    <I18nextProvider i18n={i18n}>
      <LanguageToggle />
    </I18nextProvider>,
  );
};

describe('LanguageToggle', () => {
  it('renders a select element', () => {
    renderWithI18n();
    const select = screen.getByRole('combobox');
    expect(select).toBeDefined();
  });

  it('renders both English and Telugu options', () => {
    renderWithI18n();
    expect(screen.getByText('English')).toBeDefined();
    expect(screen.getByText('తెలుగు')).toBeDefined();
  });

  it('renders a label element for accessibility', () => {
    renderWithI18n();
    const label = screen.getByLabelText('Language');
    expect(label).toBeDefined();
  });

  it('defaults to English when language is "en"', () => {
    renderWithI18n('en');
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    expect(select.value).toBe('en');
  });

  it('changes i18n language when a different option is selected', async () => {
    renderWithI18n('en');
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'te' } });
    // Allow the async changeLanguage to resolve
    await new Promise((r) => setTimeout(r, 0));
    expect(i18n.language).toBe('te');
  });

  it('shows Telugu label when language is set to "te"', async () => {
    renderWithI18n('en');
    const select = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'te' } });
    await new Promise((r) => setTimeout(r, 0));
    // The label should now display the Telugu word for "Language"
    expect(i18n.t('common.language')).toBe('భాష');
  });

  it('has exactly two language options', () => {
    renderWithI18n();
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(2);
  });
});
