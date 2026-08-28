/**
 * ChatPanel.test.tsx — Vitest unit tests for the ChatPanel component and the
 * gameStore chat slice.
 *
 * Covers:
 * - Panel renders received chat messages
 * - Sender name, colour indicator, and timestamp are rendered
 * - Empty messages cannot be submitted
 * - Input maxLength enforces the 200-character limit client-side
 * - Toggle button shows/hides the panel
 * - FIFO eviction in the store caps messages at MAX_CHAT_MESSAGES
 * - sendMessage callback is invoked with trimmed text
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { act } from 'react';

import { ChatPanel } from './ChatPanel';
import { useGameStore, MAX_CHAT_MESSAGES, ChatMessage } from '../../store/gameStore';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    timestamp: new Date().toISOString(),
    senderName: 'Alice',
    senderColor: '#e74c3c',
    text: 'Hello!',
    ...overrides,
  };
}

/** Reset the Zustand store to its initial state before each test. */
function resetStore(): void {
  act(() => {
    useGameStore.setState({ chatMessages: [], isChatOpen: true });
  });
}

// ---------------------------------------------------------------------------
// Store tests (pure logic, no DOM)
// ---------------------------------------------------------------------------

describe('gameStore — chat slice', () => {
  beforeEach(resetStore);

  it('addChatMessage appends a message', () => {
    const msg = makeMessage({ text: 'test' });
    act(() => {
      useGameStore.getState().addChatMessage(msg);
    });
    expect(useGameStore.getState().chatMessages).toHaveLength(1);
    expect(useGameStore.getState().chatMessages[0].text).toBe('test');
  });

  it('enforces FIFO cap at MAX_CHAT_MESSAGES', () => {
    act(() => {
      for (let i = 0; i < MAX_CHAT_MESSAGES + 5; i++) {
        useGameStore.getState().addChatMessage(makeMessage({ text: `msg-${i}` }));
      }
    });
    const msgs = useGameStore.getState().chatMessages;
    expect(msgs).toHaveLength(MAX_CHAT_MESSAGES);
    // Oldest messages are evicted; the newest should be the last ones added
    expect(msgs[msgs.length - 1].text).toBe(`msg-${MAX_CHAT_MESSAGES + 4}`);
    expect(msgs[0].text).toBe('msg-5');
  });

  it('toggleChat flips isChatOpen', () => {
    act(() => {
      useGameStore.setState({ isChatOpen: true });
      useGameStore.getState().toggleChat();
    });
    expect(useGameStore.getState().isChatOpen).toBe(false);

    act(() => {
      useGameStore.getState().toggleChat();
    });
    expect(useGameStore.getState().isChatOpen).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// ChatPanel rendering tests
// ---------------------------------------------------------------------------

describe('ChatPanel', () => {
  beforeEach(resetStore);

  it('renders the toggle button', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.getByTestId('chat-toggle')).toBeDefined();
  });

  it('shows the panel when isChatOpen is true', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.getByTestId('chat-panel')).toBeDefined();
  });

  it('hides the panel when isChatOpen is false', () => {
    act(() => {
      useGameStore.setState({ isChatOpen: false });
    });
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.queryByTestId('chat-panel')).toBeNull();
  });

  it('renders received messages in the message list', () => {
    act(() => {
      useGameStore.getState().addChatMessage(makeMessage({ text: 'Hi there!' }));
      useGameStore.getState().addChatMessage(makeMessage({ text: 'How are you?' }));
    });
    render(<ChatPanel sendMessage={vi.fn()} />);
    const messages = screen.getAllByTestId('chat-message');
    expect(messages).toHaveLength(2);
  });

  it('displays the sender name for each message', () => {
    act(() => {
      useGameStore.getState().addChatMessage(makeMessage({ senderName: 'Bob' }));
    });
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.getByTestId('sender-name').textContent).toBe('Bob');
  });

  it('renders a colour indicator for each message', () => {
    act(() => {
      useGameStore.getState().addChatMessage(makeMessage({ senderColor: '#3498db' }));
    });
    render(<ChatPanel sendMessage={vi.fn()} />);
    const dot = screen.getByTestId('sender-color-indicator');
    expect((dot as HTMLElement).style.backgroundColor).toBe('rgb(52, 152, 219)');
  });

  it('renders message text', () => {
    act(() => {
      useGameStore.getState().addChatMessage(makeMessage({ text: 'Roll dice!' }));
    });
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.getByTestId('message-text').textContent).toBe('Roll dice!');
  });

  it('shows the timestamp for each message', () => {
    act(() => {
      useGameStore.getState().addChatMessage(makeMessage());
    });
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.getByTestId('message-timestamp')).toBeDefined();
  });

  // -------------------------------------------------------------------------
  // Input / send interaction
  // -------------------------------------------------------------------------

  it('does not call sendMessage when input is empty', () => {
    const sendMessage = vi.fn();
    render(<ChatPanel sendMessage={sendMessage} />);
    const sendButton = screen.getByTestId('send-button');
    fireEvent.click(sendButton);
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('does not call sendMessage when input contains only whitespace', () => {
    const sendMessage = vi.fn();
    render(<ChatPanel sendMessage={sendMessage} />);
    const input = screen.getByTestId('chat-input');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(screen.getByTestId('send-button'));
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it('calls sendMessage with trimmed text on Send click', () => {
    const sendMessage = vi.fn();
    render(<ChatPanel sendMessage={sendMessage} />);
    const input = screen.getByTestId('chat-input');
    fireEvent.change(input, { target: { value: '  hello  ' } });
    fireEvent.click(screen.getByTestId('send-button'));
    expect(sendMessage).toHaveBeenCalledWith('hello');
  });

  it('calls sendMessage when Enter key is pressed', () => {
    const sendMessage = vi.fn();
    render(<ChatPanel sendMessage={sendMessage} />);
    const input = screen.getByTestId('chat-input');
    fireEvent.change(input, { target: { value: 'Enter to send' } });
    fireEvent.keyDown(input, { key: 'Enter', code: 'Enter' });
    expect(sendMessage).toHaveBeenCalledWith('Enter to send');
  });

  it('clears the input after sending', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    const input = screen.getByTestId('chat-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'hello' } });
    fireEvent.click(screen.getByTestId('send-button'));
    expect(input.value).toBe('');
  });

  it('input has maxLength of 200 to enforce client-side limit', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    const input = screen.getByTestId('chat-input') as HTMLInputElement;
    expect(input.maxLength).toBe(200);
  });

  it('send button is disabled when input is empty', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    const btn = screen.getByTestId('send-button') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
  });

  it('send button is enabled when input has text', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    const input = screen.getByTestId('chat-input');
    fireEvent.change(input, { target: { value: 'hi' } });
    const btn = screen.getByTestId('send-button') as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
  });

  // -------------------------------------------------------------------------
  // Toggle behaviour
  // -------------------------------------------------------------------------

  it('toggles the panel when the toggle button is clicked', () => {
    render(<ChatPanel sendMessage={vi.fn()} />);
    expect(screen.queryByTestId('chat-panel')).not.toBeNull();
    fireEvent.click(screen.getByTestId('chat-toggle'));
    expect(screen.queryByTestId('chat-panel')).toBeNull();
    fireEvent.click(screen.getByTestId('chat-toggle'));
    expect(screen.queryByTestId('chat-panel')).not.toBeNull();
  });
});
