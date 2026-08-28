/**
 * gameStore.ts — Zustand store for Ashta Chamma client-side state.
 *
 * Manages ephemeral chat messages received via WebSocket.  Messages are never
 * persisted to the server; the list is capped at MAX_CHAT_MESSAGES (100) to
 * prevent unbounded memory growth (FIFO eviction when the cap is exceeded).
 */

import { create } from 'zustand';

/** A single chat message broadcast by the server. */
export interface ChatMessage {
  /** ISO-8601 UTC timestamp supplied by the server. */
  timestamp: string;
  /** Display name of the player who sent the message. */
  senderName: string;
  /** Hex colour string for the player's colour indicator (e.g. "#e74c3c"). */
  senderColor: string;
  /** Plain-text message body (HTML tags already stripped server-side). */
  text: string;
}

/** Maximum number of chat messages retained in the store (FIFO). */
export const MAX_CHAT_MESSAGES = 100;

export interface GameState {
  /** Ordered list of received chat messages (oldest first). */
  chatMessages: ChatMessage[];

  /** Whether the chat panel is currently visible. */
  isChatOpen: boolean;

  /**
   * Append a new chat message, evicting the oldest entry if the cap is
   * exceeded.
   */
  addChatMessage: (msg: ChatMessage) => void;

  /** Toggle the visibility of the chat panel. */
  toggleChat: () => void;
}

export const useGameStore = create<GameState>()((set) => ({
  chatMessages: [],
  isChatOpen: true,

  addChatMessage: (msg: ChatMessage) =>
    set((state) => {
      const updated = [...state.chatMessages, msg];
      // Enforce FIFO cap: remove the oldest message when over the limit
      return {
        chatMessages:
          updated.length > MAX_CHAT_MESSAGES
            ? updated.slice(updated.length - MAX_CHAT_MESSAGES)
            : updated,
      };
    }),

  toggleChat: () =>
    set((state) => ({ isChatOpen: !state.isChatOpen })),
}));
