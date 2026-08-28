import type { DiceResult } from "../game/types";

interface DiceProps {
  result: DiceResult | null;
  canRoll: boolean;
  onRoll: () => void;
}

export function Dice({ result, canRoll, onRoll }: DiceProps) {
  return (
    <div className="dice-panel">
      <div className="shells-display">
        {result ? (
          <>
            <div className="shells-row">
              {result.shellStates.map((faceUp, i) => (
                <div key={i} className={`cowrie ${faceUp ? "cowrie-up" : "cowrie-down"}`}>
                  {faceUp ? "🐚" : "⚬"}
                </div>
              ))}
            </div>
            <div className={`dice-value ${result.isGrace ? "grace" : ""}`}>
              {result.value}
              {result.isGrace && <span className="grace-label">Grace!</span>}
            </div>
          </>
        ) : (
          <div className="shells-row empty">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="cowrie cowrie-idle">🐚</div>
            ))}
          </div>
        )}
      </div>
      <button className="roll-btn" onClick={onRoll} disabled={!canRoll}>
        {canRoll ? "🎲 Roll Shells" : "⏳ Wait..."}
      </button>
    </div>
  );
}
