import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Game } from './pages/Game';
import { Lobby } from './pages/Lobby';
import { MainMenu } from './pages/MainMenu';
import { Rules } from './pages/Rules';

export const App = (): JSX.Element => {
  const [rollTrigger, setRollTrigger] = useState(0);
  const [rollResult, setRollResult] = useState<boolean[] | null>(null);
  const [isRolling, setIsRolling] = useState(false);
  const [settleSummary, setSettleSummary] = useState<string | null>(null);

  const handleRoll = () => {
    // Simulate a server roll result: random mouth-up/down for each shell.
    const result = Array.from({ length: SHELL_COUNT }, () => Math.random() > 0.5);
    setRollResult(result);
    setIsRolling(true);
    setSettleSummary(null);
    setRollTrigger((n) => n + 1);
  };

  const handleSettled = () => {
    setIsRolling(false);
    if (rollResult !== null) {
      const mouthUp = rollResult.filter(Boolean).length;
      setSettleSummary(`Roll settled — ${mouthUp} mouth-up`);
    }
  };

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<MainMenu />} />
        <Route path="/lobby" element={<Lobby />} />
        <Route path="/rules" element={<Rules />} />
        <Route path="/game/:code" element={<Game />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
};
