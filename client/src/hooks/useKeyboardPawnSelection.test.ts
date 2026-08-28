import { describe, it, expect, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import type { KeyboardEvent } from 'react';
import { useKeyboardPawnSelection, type Pawn } from './useKeyboardPawnSelection';

/** Build a minimal React synthetic-style keyboard event for testing. */
function makeKeyEvent(key: string): KeyboardEvent {
  return {
    key,
    preventDefault: vi.fn(),
    stopPropagation: vi.fn(),
  } as unknown as KeyboardEvent;
}

const PAWNS: Pawn[] = [
  { id: 1, color: 'red', position: 5 },
  { id: 2, color: 'blue', position: 12 },
  { id: 3, color: 'green', position: 20 },
];

describe('useKeyboardPawnSelection', () => {
  it('initialises focusedPawnIndex to 0', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );
    expect(result.current.focusedPawnIndex).toBe(0);
  });

  it('ArrowRight advances focusedPawnIndex', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
    });

    expect(result.current.focusedPawnIndex).toBe(1);
  });

  it('ArrowDown advances focusedPawnIndex (same as ArrowRight)', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowDown'));
    });

    expect(result.current.focusedPawnIndex).toBe(1);
  });

  it('ArrowLeft decrements focusedPawnIndex', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    // Move to index 2 first.
    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
    });
    expect(result.current.focusedPawnIndex).toBe(2);

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowLeft'));
    });
    expect(result.current.focusedPawnIndex).toBe(1);
  });

  it('ArrowUp decrements focusedPawnIndex (same as ArrowLeft)', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
    });
    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowUp'));
    });

    expect(result.current.focusedPawnIndex).toBe(0);
  });

  it('ArrowRight wraps from last pawn to first', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    // Advance past the last pawn.
    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
    });

    expect(result.current.focusedPawnIndex).toBe(0);
  });

  it('ArrowLeft wraps from first pawn to last', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowLeft'));
    });

    expect(result.current.focusedPawnIndex).toBe(PAWNS.length - 1);
  });

  it('Enter calls onSelectPawn with the focused pawn', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    // Focus pawn at index 1 then press Enter.
    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
    });
    act(() => {
      result.current.handleKeyDown(makeKeyEvent('Enter'));
    });

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(PAWNS[1]);
  });

  it('handled keys call preventDefault and stopPropagation', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    const event = makeKeyEvent('ArrowRight');
    act(() => {
      result.current.handleKeyDown(event);
    });

    expect(event.preventDefault).toHaveBeenCalled();
    expect(event.stopPropagation).toHaveBeenCalled();
  });

  it('unhandled keys do not call preventDefault', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    const event = makeKeyEvent('Tab');
    act(() => {
      result.current.handleKeyDown(event);
    });

    expect(event.preventDefault).not.toHaveBeenCalled();
  });

  it('does nothing when legalPawns is empty', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection([], onSelect),
    );

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('Enter'));
    });

    expect(onSelect).not.toHaveBeenCalled();
    expect(result.current.focusedPawnIndex).toBe(0);
  });

  it('resetFocus sets focusedPawnIndex back to 0', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    act(() => {
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
      result.current.handleKeyDown(makeKeyEvent('ArrowRight'));
    });
    expect(result.current.focusedPawnIndex).toBe(2);

    act(() => {
      result.current.resetFocus();
    });

    expect(result.current.focusedPawnIndex).toBe(0);
  });

  it('setFocusedPawnIndex imperatively updates focused index', () => {
    const onSelect = vi.fn();
    const { result } = renderHook(() =>
      useKeyboardPawnSelection(PAWNS, onSelect),
    );

    act(() => {
      result.current.setFocusedPawnIndex(2);
    });

    expect(result.current.focusedPawnIndex).toBe(2);
  });
});
