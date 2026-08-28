import { type JSX } from 'react';

interface MainMenuProps {
  onPlay?: () => void;
  onRules?: () => void;
}

export const MainMenu = ({ onPlay, onRules }: MainMenuProps): JSX.Element => {
  return (
    <div className="main-menu">
      <h1>Ashta Chamma 3D</h1>
      <nav>
        <button type="button" onClick={onPlay}>
          Play
        </button>
        <button type="button" onClick={onRules}>
          Rules
        </button>
      </nav>
    </div>
  );
};
