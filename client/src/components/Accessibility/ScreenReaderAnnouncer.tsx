import { useEffect, useRef } from 'react';
import type { CSSProperties } from 'react';

export interface ScreenReaderAnnouncerProps {
  message: string;
  priority?: 'polite' | 'assertive';
}

/** Inline style for visually hidden but screen-reader-visible element (sr-only). */
const srOnlyStyle: CSSProperties = {
  position: 'absolute',
  width: '1px',
  height: '1px',
  padding: 0,
  margin: '-1px',
  overflow: 'hidden',
  clip: 'rect(0, 0, 0, 0)',
  whiteSpace: 'nowrap',
  borderWidth: 0,
};

/**
 * Renders a visually hidden ARIA live region to announce game events to
 * screen reader users without disrupting the visual display.
 *
 * The message is cleared and re-set on each change so that repeated identical
 * messages (e.g., "Rolled 2" twice in a row) are still announced by the screen
 * reader, which otherwise would ignore unchanged text content.
 *
 * Uses 'polite' priority by default to avoid interrupting ongoing speech;
 * pass priority='assertive' only for critical, time-sensitive announcements.
 */
export const ScreenReaderAnnouncer = ({
  message,
  priority = 'polite',
}: ScreenReaderAnnouncerProps): JSX.Element => {
  const announcerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!announcerRef.current || !message) return;

    // Clear first so screen readers re-read even if the text is identical.
    announcerRef.current.textContent = '';

    const timerId = setTimeout(() => {
      if (announcerRef.current) {
        announcerRef.current.textContent = message;
      }
    }, 50);

    return () => clearTimeout(timerId);
  }, [message]);

  return (
    <div
      ref={announcerRef}
      role="status"
      aria-live={priority}
      aria-atomic="true"
      style={srOnlyStyle}
    />
  );
};
