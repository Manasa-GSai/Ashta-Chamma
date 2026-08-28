import { useRef } from 'react';
import type { CSSProperties, MouseEvent } from 'react';

export interface MainMenuProps {
  onNewGame: () => void;
  onJoinGame: () => void;
  onSettings: () => void;
}

/** Inline style for the skip-to-content link when it is NOT focused. */
const skipLinkHiddenStyle: CSSProperties = {
  position: 'absolute',
  left: '-9999px',
  top: 'auto',
  width: '1px',
  height: '1px',
  overflow: 'hidden',
};

/** Inline style for the skip-to-content link when it IS focused. */
const skipLinkVisibleStyle: CSSProperties = {
  position: 'absolute',
  left: 0,
  top: 0,
  width: 'auto',
  height: 'auto',
  overflow: 'visible',
  zIndex: 9999,
  padding: '8px 16px',
  backgroundColor: '#000',
  color: '#fff',          // 21:1 contrast — exceeds WCAG AA 4.5:1
  textDecoration: 'none',
  fontSize: '1rem',
};

/**
 * Main menu page with full keyboard navigation and ARIA accessibility.
 *
 * Includes a skip-to-main-content link that is visually hidden until focused
 * by a keyboard user (WCAG 2.4.1 Bypass Blocks).
 *
 * All interactive elements are reachable via Tab in logical document order,
 * and have descriptive aria-label attributes so icon-only or ambiguous labels
 * are self-explanatory to screen reader users.
 */
export const MainMenu = ({
  onNewGame,
  onJoinGame,
  onSettings,
}: MainMenuProps): JSX.Element => {
  const mainContentRef = useRef<HTMLElement>(null);
  const skipLinkRef = useRef<HTMLAnchorElement>(null);

  const handleSkipToContent = (
    event: MouseEvent<HTMLAnchorElement>,
  ) => {
    event.preventDefault();
    if (mainContentRef.current) {
      mainContentRef.current.focus();
    }
  };

  const handleSkipLinkFocus = () => {
    if (skipLinkRef.current) {
      Object.assign(skipLinkRef.current.style, skipLinkVisibleStyle);
    }
  };

  const handleSkipLinkBlur = () => {
    if (skipLinkRef.current) {
      Object.assign(skipLinkRef.current.style, skipLinkHiddenStyle);
    }
  };

  return (
    <>
      {/*
       * Skip-to-content link (WCAG 2.4.1).
       * Visually hidden at rest; appears on keyboard focus so keyboard-only
       * users can skip repetitive navigation and jump directly to main content.
       */}
      <a
        ref={skipLinkRef}
        href="#main-content"
        style={skipLinkHiddenStyle}
        onFocus={handleSkipLinkFocus}
        onBlur={handleSkipLinkBlur}
        onClick={handleSkipToContent}
      >
        Skip to main content
      </a>

      <main
        id="main-content"
        ref={mainContentRef}
        tabIndex={-1}
        aria-label="Ashta Chamma main menu"
      >
        <h1>Ashta Chamma 3D</h1>

        <nav aria-label="Main menu navigation">
          <button
            type="button"
            onClick={onNewGame}
            aria-label="Start a new game"
          >
            New Game
          </button>

          <button
            type="button"
            onClick={onJoinGame}
            aria-label="Join an existing game"
          >
            Join Game
          </button>

          <button
            type="button"
            onClick={onSettings}
            aria-label="Open settings"
          >
            Settings
          </button>
        </nav>
      </main>
    </>
  );
};
