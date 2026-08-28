import type { DiceResult } from "./types";

const GRACE_VALUES = new Set([1, 4, 8]);

export function rollCowries(): DiceResult {
  const shellStates = Array.from({ length: 4 }, () => Math.random() < 0.5);
  const faceUp = shellStates.filter(Boolean).length;
  const value = faceUp === 0 ? 8 : faceUp;
  const isGrace = GRACE_VALUES.has(value);
  return { value, isGrace, shellStates };
}

export function isGraceValue(value: number): boolean {
  return GRACE_VALUES.has(value);
}
