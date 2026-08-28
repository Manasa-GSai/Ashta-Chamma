import { I18nextProvider, useTranslation } from 'react-i18next';
import i18n from './i18n/config';
import { LanguageToggle } from './components/LanguageToggle';

/**
 * Inner application shell.
 * Separated from App so that useTranslation() is called inside the
 * I18nextProvider boundary.
 */
const AppContent = (): JSX.Element => {
  const { t } = useTranslation();

  return (
    <main>
      <header>
        <LanguageToggle />
      </header>
      <h1>{t('menu.title')}</h1>
      <p>{t('menu.welcome')}</p>
    </main>
  );
};

/**
 * Root application component.
 * Wraps the entire tree in I18nextProvider so every screen has access to
 * the t() function and language-switching via LanguageToggle.
 */
export const App = (): JSX.Element => {
  return (
    <I18nextProvider i18n={i18n}>
      <AppContent />
    </I18nextProvider>
  );
};
