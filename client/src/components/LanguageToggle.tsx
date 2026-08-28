import { type JSX, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';

interface Language {
  code: string;
  label: string;
}

const LANGUAGES: Language[] = [
  { code: 'en', label: 'English' },
  { code: 'te', label: 'తెలుగు' },
  { code: 'hi', label: 'हिंदी' },
];

export const LanguageToggle = (): JSX.Element => {
  const { i18n, t } = useTranslation();

  const handleChange = (e: ChangeEvent<HTMLSelectElement>) => {
    // Fire-and-forget; errors are handled by i18next internally
    void i18n.changeLanguage(e.target.value);
  };

  return (
    <div className="language-toggle">
      <label htmlFor="language-select">{t('language', 'Language')}</label>
      <select
        id="language-select"
        value={i18n.language}
        onChange={handleChange}
        aria-label="Select language"
      >
        {LANGUAGES.map((lang) => (
          <option key={lang.code} value={lang.code}>
            {lang.label}
          </option>
        ))}
      </select>
    </div>
  );
};
