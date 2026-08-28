import { useCallback, useEffect, useRef, useState } from "react";
import type { GameState } from "../game/types";
import {
  createGame,
  performRoll,
  executeMove,
  getValidMoves,
  aiPickMove,
} from "../game/engine";
import { Board } from "./Board";
import { Dice } from "./Dice";

export function GamePage() {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [playerCount, setPlayerCount] = useState(2);
  const [humanCount, setHumanCount] = useState(1);
  const aiTimerRef = useRef<ReturnType<typeof setTimeout>>();

  const startGame = useCallback(() => {
    const humanIndices = Array.from({ length: humanCount }, (_, i) => i);
    setGameState(createGame({ playerCount, humanIndices }));
  }, [playerCount, humanCount]);

  const handleRoll = useCallback(() => {
    setGameState((prev) => {
      if (!prev || prev.phase !== "rolling") return prev;
      return performRoll(prev);
    });
  }, []);

  const handleMove = useCallback((pawnId: string, target: number) => {
    setGameState((prev) => {
      if (!prev || prev.phase !== "moving") return prev;
      return executeMove(prev, pawnId, target);
    });
  }, []);

  const handleSelectPawn = useCallback((pawnId: string) => {
    setGameState((prev) => {
      if (!prev || prev.phase !== "moving") return prev;
      return { ...prev, selectedPawnId: pawnId };
    });
  }, []);

  useEffect(() => {
    if (!gameState || gameState.phase === "gameover") return;
    const current = gameState.players[gameState.currentPlayerIndex];
    if (!current.isAI) return;

    if (gameState.phase === "rolling") {
      aiTimerRef.current = setTimeout(() => handleRoll(), 600);
    } else if (gameState.phase === "moving") {
      const move = aiPickMove(gameState);
      if (move) {
        aiTimerRef.current = setTimeout(
          () => handleMove(move.pawnId, move.target),
          800,
        );
      }
    }
    return () => clearTimeout(aiTimerRef.current);
  }, [gameState, handleRoll, handleMove]);

  if (!gameState) {
    return (
      <div className="setup-screen">
        <h1 className="game-title">✦ Ashta Chamma ✦</h1>
        <p className="game-subtitle">The Ancient Indian Board Game</p>
        <div className="setup-form">
          <label>
            Players
            <select value={playerCount} onChange={(e) => { const n = Number(e.target.value); setPlayerCount(n); setHumanCount(Math.min(humanCount, n)); }}>
              <option value={2}>2 Players</option>
              <option value={3}>3 Players</option>
              <option value={4}>4 Players</option>
            </select>
          </label>
          <label>
            Human Players
            <select value={humanCount} onChange={(e) => setHumanCount(Number(e.target.value))}>
              {Array.from({ length: playerCount }, (_, i) => (
                <option key={i} value={i + 1}>{i + 1}</option>
              ))}
            </select>
          </label>
          <button className="start-btn" onClick={startGame}>Start Game</button>
        </div>
        <div className="rules-summary">
          <h3>How to Play</h3>
          <ul>
            <li>Roll cowrie shells to move your pawns around the board</li>
            <li><strong>Grace rolls</strong> (1, 4, or 8) let you enter a new pawn and give an extra turn</li>
            <li>Land on an opponent to capture them (except on safe ✦ squares)</li>
            <li>Get all 4 pawns to the center to win!</li>
          </ul>
        </div>
      </div>
    );
  }

  const currentPlayer = gameState.players[gameState.currentPlayerIndex];
  const validMoves = gameState.phase === "moving" ? getValidMoves(gameState) : [];

  return (
    <div className="game-container">
      <div className="game-header">
        <h1 className="game-title-sm">Ashta Chamma</h1>
        {gameState.phase === "gameover" ? (
          <div className="winner-banner">🎉 {gameState.players[gameState.winner!].name} Wins! 🎉</div>
        ) : (
          <div className="turn-indicator" style={{ borderColor: `var(--color-${currentPlayer.color})` }}>
            <span className="turn-dot" style={{ backgroundColor: `var(--color-${currentPlayer.color})` }} />
            {currentPlayer.name}&apos;s Turn
            {currentPlayer.isAI && " (AI thinking...)"}
          </div>
        )}
      </div>
      <div className="game-layout">
        <div className="board-area">
          <Board gameState={gameState} validMoves={validMoves} onSelectPawn={handleSelectPawn} onMove={handleMove} />
        </div>
        <div className="side-panel">
          <Dice result={gameState.diceResult} canRoll={gameState.phase === "rolling" && !currentPlayer.isAI} onRoll={handleRoll} />
          <div className="players-panel">
            {gameState.players.map((pl) => (
              <div key={pl.index} className={`player-card ${pl.index === gameState.currentPlayerIndex ? "active" : ""}`} style={{ borderLeftColor: `var(--color-${pl.color})` }}>
                <div className="player-name">{pl.name}{pl.isAI && <span className="ai-badge">AI</span>}</div>
                <div className="player-pawns-status">
                  {pl.pawns.map((pawn) => (
                    <span key={pawn.id} className={`pawn-indicator ${pawn.pathIndex > 24 ? "finished" : pawn.pathIndex >= 0 ? "active" : "home"}`} style={{ backgroundColor: `var(--color-${pl.color})` }} />
                  ))}
                  <span className="finished-count">{pl.finishedCount}/4 home</span>
                </div>
              </div>
            ))}
          </div>
          <div className="game-log">
            <h4>Game Log</h4>
            <div className="log-entries">
              {gameState.log.slice(-8).reverse().map((entry, i) => (
                <div key={i} className="log-entry">{entry}</div>
              ))}
            </div>
          </div>
          {gameState.phase === "gameover" && (
            <button className="start-btn" onClick={() => setGameState(null)}>New Game</button>
          )}
        </div>
      </div>
    </div>
  );
}
