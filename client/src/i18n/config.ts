import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import en from './locales/en.json';
import te from './locales/te.json';

/** localStorage key for persisting the user's language preference. */
export const LANGUAGE_STORAGE_KEY = 'ashta-chamma-lang';

export const SUPPORTED_LANGUAGES = ['en', 'te'] as const;
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

/** Bundled translation resources — no async loading required. */
export const resources = {
  en: { translation: en },
  te: { translation: te },
} as const;

/** Read the persisted language preference, falling back to English. */
const getSavedLanguage = (): string => {
  try {
    return localStorage.getItem(LANGUAGE_STORAGE_KEY) ?? 'en';
  } catch {
    // localStorage may be unavailable (e.g. private browsing on some browsers)
    return 'en';
  }
};

void i18n.use(initReactI18next).init({
  resources,
  lng: getSavedLanguage(),
  fallbackLng: 'en',
  // React already escapes values — no double-escaping needed
  interpolation: { escapeValue: false },
  // Resources are bundled inline, so initialisation is synchronous.
  // initImmediate was removed in i18next v23+ — omitting it is the correct
  // way to request synchronous init when resources are pre-loaded.
});

// Persist language choice whenever the user switches languages
i18n.on('languageChanged', (lng: string) => {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, lng);
  } catch {
    // Silently ignore write failures (quota exceeded, private mode, etc.)
  }
});

export default i18n;
