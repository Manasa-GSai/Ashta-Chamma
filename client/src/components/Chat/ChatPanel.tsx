/**
 * ChatPanel.tsx — collapsible in-game text chat overlay.
 *
 * Positioned as a semi-transparent overlay at the bottom-right of the game
 * screen.  The panel can be toggled open/closed so it never permanently
 * obstructs the game board.
 *
 * Messages are displayed with the sender's display name, their player-colour
 * indicator dot, and a formatted timestamp.  The input field sanitizes the
 * text client-side (trim + max-length) before sending; the server performs
 * definitive sanitization (HTML-tag stripping) before broadcast.
 *
 * Props:
 *   sendMessage — callback invoked when the user submits a chat message.
 *                 Receives the raw (trimmed) text string.  The caller is
 *                 responsible for forwarding it over the WebSocket.
 */

import React, { KeyboardEvent, useRef, useEffect, useState } from 'react';
import { useGameStore, ChatMessage } from '../../store/gameStore';

/** Maximum characters the input enforces client-side (mirrors server limit). */
const MAX_INPUT_LENGTH = 200;

/**
 * Format an ISO-8601 timestamp into a human-readable HH:MM string (local
 * time).  Falls back to the raw string if parsing fails.
 */
function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
  } catch {
    return iso;
  }
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface MessageRowProps {
  message: ChatMessage;
}

/** Renders a single chat message row. */
function MessageRow({ message }: MessageRowProps): JSX.Element {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '6px',
        padding: '4px 0',
        wordBreak: 'break-word',
      }}
      data-testid="chat-message"
    >
      {/* Player colour indicator */}
      <span
        aria-hidden="true"
        style={{
          flexShrink: 0,
          width: '10px',
          height: '10px',
          borderRadius: '50%',
          backgroundColor: message.senderColor,
          marginTop: '3px',
        }}
        data-testid="sender-color-indicator"
      />
      <div style={{ fontSize: '13px', lineHeight: '1.4' }}>
        <span
          style={{ fontWeight: 600, marginRight: '4px' }}
          data-testid="sender-name"
        >
          {message.senderName}
        </span>
        <span
          style={{ color: 'rgba(255,255,255,0.55)', fontSize: '11px', marginRight: '6px' }}
          data-testid="message-timestamp"
        >
          {formatTime(message.timestamp)}
        </span>
        <span data-testid="message-text">{message.text}</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export interface ChatPanelProps {
  /** Called when the user submits a message; the caller sends it via WS. */
  sendMessage: (text: string) => void;
}

/**
 * ChatPanel — semi-transparent chat overlay positioned at the bottom-right of
 * the game screen.  Collapses to a small toggle button when closed.
 */
export function ChatPanel({ sendMessage }: ChatPanelProps): JSX.Element {
  const chatMessages = useGameStore((s) => s.chatMessages);
  const isChatOpen = useGameStore((s) => s.isChatOpen);
  const toggleChat = useGameStore((s) => s.toggleChat);

  const [inputValue, setInputValue] = useState('');
  const messageListRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to the bottom whenever a new message arrives while the panel
  // is open.
  useEffect(() => {
    if (isChatOpen && messageListRef.current) {
      messageListRef.current.scrollTop = messageListRef.current.scrollHeight;
    }
  }, [chatMessages, isChatOpen]);

  /** Submit the current input value as a chat message. */
  function handleSend(): void {
    const trimmed = inputValue.trim().slice(0, MAX_INPUT_LENGTH);
    if (!trimmed) return; // AC5: empty messages cannot be sent
    sendMessage(trimmed);
    setInputValue('');
  }

  /** Allow submitting with Enter (Shift+Enter inserts a newline — not
   *  applicable here since the input is a single-line field, but we guard
   *  shift-enter for completeness). */
  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  // ---------------------------------------------------------------------------
  // Panel styles — semi-transparent overlay, bottom-right, non-blocking
  // ---------------------------------------------------------------------------
  const overlayStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: '16px',
    right: '16px',
    zIndex: 100,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'flex-end',
    gap: '4px',
    // Pointer events limited to the panel itself; clicks on the game board
    // outside the panel pass through normally (see pointerEvents on children).
    pointerEvents: 'none',
  };

  const panelStyle: React.CSSProperties = {
    pointerEvents: 'auto',
    width: '300px',
    maxHeight: '360px',
    display: 'flex',
    flexDirection: 'column',
    backgroundColor: 'rgba(15, 15, 25, 0.80)',
    backdropFilter: 'blur(6px)',
    borderRadius: '10px',
    border: '1px solid rgba(255,255,255,0.12)',
    overflow: 'hidden',
    color: '#f0f0f0',
    fontFamily: 'system-ui, sans-serif',
  };

  const toggleButtonStyle: React.CSSProperties = {
    pointerEvents: 'auto',
    cursor: 'pointer',
    padding: '6px 14px',
    borderRadius: '20px',
    border: '1px solid rgba(255,255,255,0.20)',
    backgroundColor: 'rgba(15, 15, 25, 0.80)',
    backdropFilter: 'blur(6px)',
    color: '#f0f0f0',
    fontSize: '13px',
    fontFamily: 'system-ui, sans-serif',
    userSelect: 'none',
  };

  return (
    <div style={overlayStyle} data-testid="chat-overlay">
      {/* Collapsible panel body */}
      {isChatOpen && (
        <div style={panelStyle} data-testid="chat-panel">
          {/* Header */}
          <div
            style={{
              padding: '8px 12px',
              borderBottom: '1px solid rgba(255,255,255,0.10)',
              fontWeight: 600,
              fontSize: '13px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <span>Chat</span>
            <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: '11px' }}>
              {chatMessages.length} message{chatMessages.length !== 1 ? 's' : ''}
            </span>
          </div>

          {/* Message list */}
          <div
            ref={messageListRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              padding: '6px 12px',
              minHeight: '120px',
              maxHeight: '260px',
            }}
            data-testid="message-list"
            aria-live="polite"
            aria-label="Chat messages"
          >
            {chatMessages.length === 0 ? (
              <p
                style={{
                  color: 'rgba(255,255,255,0.35)',
                  fontSize: '12px',
                  textAlign: 'center',
                  marginTop: '20px',
                }}
              >
                No messages yet
              </p>
            ) : (
              chatMessages.map((msg, idx) => (
                <MessageRow key={`${msg.timestamp}-${idx}`} message={msg} />
              ))
            )}
          </div>

          {/* Input area */}
          <div
            style={{
              display: 'flex',
              borderTop: '1px solid rgba(255,255,255,0.10)',
              padding: '8px',
              gap: '6px',
            }}
          >
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              maxLength={MAX_INPUT_LENGTH}
              placeholder="Type a message…"
              aria-label="Chat message input"
              data-testid="chat-input"
              style={{
                flex: 1,
                background: 'rgba(255,255,255,0.08)',
                border: '1px solid rgba(255,255,255,0.15)',
                borderRadius: '6px',
                padding: '6px 10px',
                color: '#f0f0f0',
                fontSize: '13px',
                outline: 'none',
              }}
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!inputValue.trim()}
              aria-label="Send chat message"
              data-testid="send-button"
              style={{
                padding: '6px 12px',
                borderRadius: '6px',
                border: 'none',
                backgroundColor: inputValue.trim() ? '#4a9eed' : 'rgba(74,158,237,0.35)',
                color: '#fff',
                cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
                fontSize: '13px',
                fontWeight: 600,
                transition: 'background-color 0.15s',
              }}
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* Toggle button */}
      <button
        type="button"
        onClick={toggleChat}
        style={toggleButtonStyle}
        aria-expanded={isChatOpen}
        aria-controls="chat-panel"
        data-testid="chat-toggle"
      >
        {isChatOpen ? '✕ Hide Chat' : '💬 Chat'}
      </button>
    </div>
  );
}
