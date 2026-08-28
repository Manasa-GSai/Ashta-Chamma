import { pathToPosition, isSafe, isCenter, posKey, PATH_LENGTH } from "./board";
import { rollCowries } from "./dice";
import type { GameState, Player, Pawn, PlayerColor } from "./types";
import { PLAYER_COLORS } from "./types";

const PAWNS_PER_PLAYER = 4;
const MAX_CONSECUTIVE_GRACES = 3;

function makePawns(playerIndex: number): Pawn[] {
  return Array.from({ length: PAWNS_PER_PLAYER }, (_, i) => ({
    id: `p${playerIndex}-${i}`,
    playerIndex,
    pathIndex: -1,
  }));
}

function makePlayer(
  index: number,
  name: string,
  color: PlayerColor,
  isAI: boolean,
): Player {
  return {
    index,
    name,
    color,
    isAI,
    pawns: makePawns(index),
    finishedCount: 0,
  };
}

export interface GameSetup {
  playerCount: number;
  humanIndices: number[];
  names?: string[];
}

export function createGame(setup: GameSetup): GameState {
  const aiNames = ["Bala", "Kamala", "Surya", "Devi"];
  let aiIdx = 0;
  const players: Player[] = [];

  for (let i = 0; i < setup.playerCount; i++) {
    const isHuman = setup.humanIndices.includes(i);
    const name =
      setup.names?.[i] ??
      (isHuman ? `Player ${i + 1}` : aiNames[aiIdx++] ?? `AI ${i + 1}`);
    players.push(makePlayer(i, name, PLAYER_COLORS[i], !isHuman));
  }

  return {
    players,
    currentPlayerIndex: 0,
    diceResult: null,
    phase: "rolling",
    selectedPawnId: null,
    winner: null,
    log: ["Game started!"],
    consecutiveGraces: 0,
  };
}

function buildBoardMap(
  players: Player[],
): Map<string, { playerIndex: number; pawnId: string }[]> {
  const map = new Map<string, { playerIndex: number; pawnId: string }[]>();
  for (const player of players) {
    for (const pawn of player.pawns) {
      if (pawn.pathIndex < 0 || pawn.pathIndex > PATH_LENGTH) continue;
      const pos = pathToPosition(player.index, pawn.pathIndex);
      if (!pos) continue;
      const key = posKey(pos);
      const list = map.get(key) ?? [];
      list.push({ playerIndex: player.index, pawnId: pawn.id });
      map.set(key, list);
    }
  }
  return map;
}

export interface ValidMove {
  pawnId: string;
  targetPathIndex: number;
}

export function getValidMoves(state: GameState): ValidMove[] {
  const dice = state.diceResult;
  if (!dice) return [];

  const player = state.players[state.currentPlayerIndex];
  const boardMap = buildBoardMap(state.players);
  const moves: ValidMove[] = [];

  for (const pawn of player.pawns) {
    if (pawn.pathIndex > PATH_LENGTH) continue;

    if (pawn.pathIndex === -1) {
      if (!dice.isGrace) continue;
      const entryPos = pathToPosition(player.index, 0)!;
      const entryKey = posKey(entryPos);
      const occupants = boardMap.get(entryKey) ?? [];
      const enemyBlock = occupants.filter(
        (o) => o.playerIndex !== player.index,
      );
      if (enemyBlock.length >= 2) continue;
      moves.push({ pawnId: pawn.id, targetPathIndex: 0 });
      continue;
    }

    const target = pawn.pathIndex + dice.value;
    if (target > PATH_LENGTH) continue;

    const targetPos = pathToPosition(player.index, target)!;
    const targetKey = posKey(targetPos);
    const occupants = boardMap.get(targetKey) ?? [];
    const enemyOccupants = occupants.filter(
      (o) => o.playerIndex !== player.index,
    );

    if (enemyOccupants.length >= 2) continue;

    moves.push({ pawnId: pawn.id, targetPathIndex: target });
  }

  return moves;
}

export function performRoll(state: GameState): GameState {
  const dice = rollCowries();
  const player = state.players[state.currentPlayerIndex];
  const next: GameState = {
    ...state,
    diceResult: dice,
    phase: "moving",
    selectedPawnId: null,
    log: [
      ...state.log,
      `${player.name} rolled ${dice.value}${dice.isGrace ? " (grace!)" : ""}`,
    ],
  };

  const moves = getValidMoves(next);
  if (moves.length === 0) {
    return advanceTurn({
      ...next,
      log: [...next.log, `${player.name} has no valid moves — turn passes.`],
      consecutiveGraces: 0,
    });
  }

  if (moves.length === 1) {
    return { ...next, selectedPawnId: moves[0].pawnId };
  }

  return next;
}

export function executeMove(
  state: GameState,
  pawnId: string,
  targetPathIndex: number,
): GameState {
  const playerIdx = state.currentPlayerIndex;
  const player = state.players[playerIdx];
  const pawn = player.pawns.find((p) => p.id === pawnId);
  if (!pawn) return state;

  const newPlayers = state.players.map((pl) => ({
    ...pl,
    pawns: pl.pawns.map((p) => ({ ...p })),
  }));
  const movingPawn = newPlayers[playerIdx].pawns.find((p) => p.id === pawnId)!;
  const targetPos = pathToPosition(playerIdx, targetPathIndex)!;
  const targetKey = posKey(targetPos);
  const log = [...state.log];
  let extraTurn = state.diceResult?.isGrace ?? false;

  if (!isSafe(targetPos) && !isCenter(targetPos)) {
    for (const otherPlayer of newPlayers) {
      if (otherPlayer.index === playerIdx) continue;
      for (const otherPawn of otherPlayer.pawns) {
        if (otherPawn.pathIndex < 0) continue;
        const otherPos = pathToPosition(otherPlayer.index, otherPawn.pathIndex);
        if (otherPos && posKey(otherPos) === targetKey) {
          const sameSquare = otherPlayer.pawns.filter((op) => {
            if (op.pathIndex < 0) return false;
            const oPos = pathToPosition(otherPlayer.index, op.pathIndex);
            return oPos && posKey(oPos) === targetKey;
          });
          if (sameSquare.length < 2) {
            otherPawn.pathIndex = -1;
            log.push(`${player.name} captured ${otherPlayer.name}'s pawn!`);
            extraTurn = true;
          }
        }
      }
    }
  }

  movingPawn.pathIndex = targetPathIndex;

  if (targetPathIndex === PATH_LENGTH) {
    newPlayers[playerIdx].finishedCount += 1;
    movingPawn.pathIndex = PATH_LENGTH + 1;
    log.push(`${player.name} got a pawn home!`);

    if (newPlayers[playerIdx].finishedCount === PAWNS_PER_PLAYER) {
      return {
        ...state,
        players: newPlayers,
        phase: "gameover",
        winner: playerIdx,
        diceResult: null,
        selectedPawnId: null,
        log: [...log, `🎉 ${player.name} wins the game!`],
        consecutiveGraces: 0,
      };
    }
  }

  const newConsecutive = extraTurn ? state.consecutiveGraces + 1 : 0;
  if (extraTurn && newConsecutive >= MAX_CONSECUTIVE_GRACES) {
    log.push(`${player.name} hit ${MAX_CONSECUTIVE_GRACES} graces in a row — turn passes.`);
    extraTurn = false;
  }

  if (extraTurn) {
    log.push(`${player.name} gets another turn!`);
    return {
      ...state,
      players: newPlayers,
      diceResult: null,
      phase: "rolling",
      selectedPawnId: null,
      log,
      consecutiveGraces: newConsecutive,
    };
  }

  return advanceTurn({
    ...state,
    players: newPlayers,
    diceResult: null,
    selectedPawnId: null,
    log,
    consecutiveGraces: 0,
  });
}

function advanceTurn(state: GameState): GameState {
  const next = (state.currentPlayerIndex + 1) % state.players.length;
  return {
    ...state,
    currentPlayerIndex: next,
    phase: "rolling",
    diceResult: null,
    selectedPawnId: null,
  };
}

export function aiPickMove(
  state: GameState,
): { pawnId: string; target: number } | null {
  const moves = getValidMoves(state);
  if (moves.length === 0) return null;

  const playerIdx = state.currentPlayerIndex;

  const finishMoves = moves.filter((m) => m.targetPathIndex === PATH_LENGTH);
  if (finishMoves.length > 0) {
    const pick = finishMoves[Math.floor(Math.random() * finishMoves.length)];
    return { pawnId: pick.pawnId, target: pick.targetPathIndex };
  }

  const captureMoves = moves.filter((m) => {
    const pos = pathToPosition(playerIdx, m.targetPathIndex);
    if (!pos || isSafe(pos)) return false;
    for (const other of state.players) {
      if (other.index === playerIdx) continue;
      for (const op of other.pawns) {
        if (op.pathIndex < 0) continue;
        const oPos = pathToPosition(other.index, op.pathIndex);
        if (oPos && posKey(oPos) === posKey(pos)) return true;
      }
    }
    return false;
  });
  if (captureMoves.length > 0) {
    const pick = captureMoves[Math.floor(Math.random() * captureMoves.length)];
    return { pawnId: pick.pawnId, target: pick.targetPathIndex };
  }

  const pick = moves[Math.floor(Math.random() * moves.length)];
  return { pawnId: pick.pawnId, target: pick.targetPathIndex };
}
