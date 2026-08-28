import { BOARD_SIZE, isSafe, isCenter, pathToPosition, posKey } from "../game/board";
import type { GameState } from "../game/types";
import { COLOR_HEX } from "../game/types";
import type { ValidMove } from "../game/engine";

interface BoardProps {
  gameState: GameState;
  validMoves: ValidMove[];
  onSelectPawn: (pawnId: string) => void;
  onMove: (pawnId: string, target: number) => void;
}

interface CellPawnInfo {
  pawnId: string;
  playerIndex: number;
  color: string;
  isSelected: boolean;
  canMove: boolean;
  targetPathIndex: number | null;
}

export function Board({ gameState, validMoves, onSelectPawn, onMove }: BoardProps) {
  const cellPawns = new Map<string, CellPawnInfo[]>();
  const moveTargetCells = new Set<string>();

  for (const player of gameState.players) {
    for (const pawn of player.pawns) {
      if (pawn.pathIndex < 0 || pawn.pathIndex > 24) continue;
      const pos = pathToPosition(player.index, pawn.pathIndex);
      if (!pos) continue;
      const key = posKey(pos);
      const move = validMoves.find((m) => m.pawnId === pawn.id);
      const info: CellPawnInfo = {
        pawnId: pawn.id,
        playerIndex: player.index,
        color: COLOR_HEX[player.color],
        isSelected: pawn.id === gameState.selectedPawnId,
        canMove: !!move,
        targetPathIndex: move?.targetPathIndex ?? null,
      };
      const list = cellPawns.get(key) ?? [];
      list.push(info);
      cellPawns.set(key, list);
    }
  }

  if (gameState.selectedPawnId) {
    const move = validMoves.find((m) => m.pawnId === gameState.selectedPawnId);
    if (move) {
      const currentPlayer = gameState.players[gameState.currentPlayerIndex];
      const pos = pathToPosition(currentPlayer.index, move.targetPathIndex);
      if (pos) moveTargetCells.add(posKey(pos));
    }
  }

  const offBoardPawns = gameState.players.map((pl) => {
    const offBoard = pl.pawns.filter((p) => p.pathIndex === -1);
    const canEnter = validMoves.some(
      (m) => m.targetPathIndex === 0 && offBoard.some((ob) => ob.id === m.pawnId),
    );
    return { player: pl, pawns: offBoard, canEnter };
  });

  const handleCellClick = (key: string) => {
    if (moveTargetCells.has(key) && gameState.selectedPawnId) {
      const move = validMoves.find((m) => m.pawnId === gameState.selectedPawnId);
      if (move) { onMove(move.pawnId, move.targetPathIndex); return; }
    }
    const pawnsHere = cellPawns.get(key) ?? [];
    const myPawn = pawnsHere.find(
      (p) => p.playerIndex === gameState.currentPlayerIndex && p.canMove,
    );
    if (myPawn) onSelectPawn(myPawn.pawnId);
  };

  const handleOffBoardClick = (pawnId: string) => {
    const move = validMoves.find((m) => m.pawnId === pawnId);
    if (move) {
      if (gameState.selectedPawnId === pawnId) {
        onMove(pawnId, move.targetPathIndex);
      } else {
        onSelectPawn(pawnId);
      }
    }
  };

  const rows = [];
  for (let r = 0; r < BOARD_SIZE; r++) {
    const cells = [];
    for (let c = 0; c < BOARD_SIZE; c++) {
      const key = `${r},${c}`;
      const pos = { row: r, col: c };
      const safe = isSafe(pos);
      const center = isCenter(pos);
      const pawnsHere = cellPawns.get(key) ?? [];
      const isTarget = moveTargetCells.has(key);

      cells.push(
        <div
          key={key}
          className={["cell", safe ? "cell-safe" : "", center ? "cell-center" : "", isTarget ? "cell-target" : ""].filter(Boolean).join(" ")}
          onClick={() => handleCellClick(key)}
        >
          {safe && !center && <span className="safe-mark">✦</span>}
          {center && <span className="center-mark">⬟</span>}
          <div className="cell-pawns">
            {pawnsHere.map((pi, idx) => (
              <div
                key={pi.pawnId}
                className={["pawn", pi.isSelected ? "pawn-selected" : "", pi.canMove ? "pawn-movable" : ""].filter(Boolean).join(" ")}
                style={{
                  backgroundColor: pi.color,
                  transform: pawnsHere.length > 1
                    ? `translate(${(idx % 2) * 14 - 7}px, ${Math.floor(idx / 2) * 14 - 7}px)`
                    : undefined,
                }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (pi.canMove) {
                    if (pi.isSelected && pi.targetPathIndex !== null) {
                      onMove(pi.pawnId, pi.targetPathIndex);
                    } else {
                      onSelectPawn(pi.pawnId);
                    }
                  }
                }}
              />
            ))}
          </div>
        </div>,
      );
    }
    rows.push(<div key={r} className="board-row">{cells}</div>);
  }

  return (
    <div className="board-wrapper">
      <div className="pawn-trays">
        {offBoardPawns.map(({ player, pawns, canEnter }) =>
          pawns.length > 0 ? (
            <div key={player.index} className={`pawn-tray tray-${player.color}`}>
              <span className="tray-label">{player.name}</span>
              <div className="tray-pawns">
                {pawns.map((pawn) => {
                  const isSelected = pawn.id === gameState.selectedPawnId;
                  const pawnCanEnter = canEnter && validMoves.some((m) => m.pawnId === pawn.id);
                  return (
                    <div
                      key={pawn.id}
                      className={["pawn pawn-home", pawnCanEnter ? "pawn-movable" : "", isSelected ? "pawn-selected" : ""].filter(Boolean).join(" ")}
                      style={{ backgroundColor: COLOR_HEX[player.color] }}
                      onClick={() => pawnCanEnter && handleOffBoardClick(pawn.id)}
                    />
                  );
                })}
              </div>
            </div>
          ) : null,
        )}
      </div>
      <div className="board-grid">{rows}</div>
    </div>
  );
}
