/**
 * Locale-aware formatting utilities using the built-in Intl API.
 * Pass the i18n language code (e.g. 'en', 'te') as the locale parameter;
 * these are valid BCP 47 language tags accepted by all Intl constructors.
 */

/**
 * Formats a number according to the given locale's conventions.
 * Example: formatNumber(1000, 'en') → "1,000"
 *          formatNumber(1000, 'te') → locale-specific representation
 */
export const formatNumber = (value: number, locale: string): string => {
  return new Intl.NumberFormat(locale).format(value);
};

/**
 * Formats a Date as a long-form date string (year, month name, day) for
 * the given locale.
 * Example: formatDate(new Date(2024, 0, 15), 'en') → "January 15, 2024"
 */
export const formatDate = (date: Date, locale: string): string => {
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(date);
};

/**
 * Formats a Date as a short date + time string for the given locale.
 * Example: formatDateTime(new Date(2024, 0, 15, 10, 30), 'en') →
 *          "Jan 15, 2024, 10:30 AM"
 */
export const formatDateTime = (date: Date, locale: string): string => {
  return new Intl.DateTimeFormat(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
};
