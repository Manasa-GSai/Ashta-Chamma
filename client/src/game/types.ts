export interface Position {
  row: number;
  col: number;
}

export type PlayerColor = "blue" | "red" | "green" | "yellow";

export const PLAYER_COLORS: PlayerColor[] = ["blue", "red", "green", "yellow"];
export const COLOR_HEX: Record<PlayerColor, string> = {
  blue: "#2563eb",
  red: "#dc2626",
  green: "#16a34a",
  yellow: "#ca8a04",
};

export interface Pawn {
  id: string;
  playerIndex: number;
  pathIndex: number;
}

export interface Player {
  index: number;
  name: string;
  color: PlayerColor;
  isAI: boolean;
  pawns: Pawn[];
  finishedCount: number;
}

export interface DiceResult {
  value: number;
  isGrace: boolean;
  shellStates: boolean[];
}

export type GamePhase = "setup" | "rolling" | "moving" | "gameover";

export interface GameState {
  players: Player[];
  currentPlayerIndex: number;
  diceResult: DiceResult | null;
  phase: GamePhase;
  selectedPawnId: string | null;
  winner: number | null;
  log: string[];
  consecutiveGraces: number;
}
