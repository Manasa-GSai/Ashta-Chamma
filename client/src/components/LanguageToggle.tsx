import { useTranslation } from 'react-i18next';
import { SUPPORTED_LANGUAGES, type SupportedLanguage } from '../i18n/config';

/** Human-readable display labels for each supported locale. */
const LANGUAGE_LABELS: Record<SupportedLanguage, string> = {
  en: 'English',
  te: 'తెలుగు',
};

/**
 * Language toggle dropdown rendered on every screen.
 * Calls i18n.changeLanguage() so all visible text updates immediately
 * without a page reload. The preference is persisted via the listener
 * registered in i18n/config.ts.
 */
export const LanguageToggle = (): JSX.Element => {
  const { i18n, t } = useTranslation();

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>): void => {
    void i18n.changeLanguage(event.target.value);
  };

  return (
    <div className="language-toggle">
      <label htmlFor="language-select">{t('common.language')}</label>
      <select
        id="language-select"
        value={i18n.language}
        onChange={handleChange}
        aria-label={t('common.language')}
      >
        {SUPPORTED_LANGUAGES.map((code) => (
          <option key={code} value={code}>
            {LANGUAGE_LABELS[code]}
          </option>
        ))}
      </select>
    </div>
  );
};
