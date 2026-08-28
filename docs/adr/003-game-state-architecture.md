# ADR-003: Server-Authoritative Finite State Machine for Game Logic

**Status:** Accepted

**Date:** 2025-01-27

## Context

The Ashta Chamma game has complex rules: cowrie roll resolution, pawn entry
conditions, capture logic, safe squares, home-stretch exact-count rules, and
win detection. In a multiplayer context, the game state must be consistent
across all connected clients. There are two broad strategies for state ownership:

| Strategy | Description | Risk |
|---|---|---|
| Client-authoritative | Each client runs game logic; state is shared peer-to-peer or via a thin relay | Cheating, desyncs, trust boundary unclear |
| **Server-authoritative** (chosen) | Server owns all game state; clients send intents; server validates and broadcasts state | Latency for every action; simpler client |

Additionally, the game progresses through a well-defined lifecycle (waiting →
rolling → selecting → moving → game_over) that is best modelled as an explicit
finite state machine (FSM) rather than ad-hoc boolean flags (the legacy approach
in `game.py`).

## Decision

We will implement the game as a **server-authoritative finite state machine** in
Python on the FastAPI backend.

**FSM States:**

| State | Meaning |
|---|---|
| `WAITING` | Room created; waiting for all players to join |
| `ROLLING` | Current player's turn to roll cowries |
| `SELECTING` | Roll complete; player must select a pawn to move |
| `MOVING` | Server has committed the move; clients animate |
| `GAME_OVER` | A player moved all 4 pawns home; game is terminal |

**Responsibilities split:**

- **Server**: Generates cowrie rolls (using `secrets.SystemRandom` for fairness),
  validates all moves, advances FSM state, persists results to PostgreSQL on
  game end, publishes state deltas to Redis pub/sub.
- **Client**: Renders the current state received from the server. Sends intent
  messages (`roll_request`, `select_pawn`). Runs animations locally for
  visual polish but never mutates authoritative state.

The FSM is implemented as a Python `enum`-based class (`GameStateMachine`) living
in `server/app/game/state_machine.py`. It is the single source of truth; no game
logic runs anywhere else.

## Consequences

### Positive

- **Anti-cheat**: Clients cannot forge roll results or move pawns illegally.
- **Consistency**: All players see exactly the same state snapshot after every
  transition.
- **Testability**: The FSM is pure Python with no I/O; 100 % unit test coverage
  is straightforward.
- **Auditability**: Every state transition can be logged for debugging or replay.
- **AI integration**: AI opponents run server-side within the same FSM, with no
  network round-trip needed for AI moves.

### Negative

- Every player action requires a round-trip to the server before the game advances.
  At p95 WebSocket latency < 100 ms this is imperceptible for a turn-based game.
- The server is a single point of logic; a Fargate task crash mid-game loses the
  in-memory FSM state unless Redis state is checkpointed.
  Mitigation: Redis stores the full serialized game state after every transition.

### Risks

- **State desync**: If a Redis publish fails silently, some clients may miss a
  state update. Mitigated by including a monotonically-increasing sequence number
  in every state update; clients request a full resync if they detect a gap.
- **Reconnect recovery**: A player who disconnects must receive a full state
  snapshot on reconnect. Mitigated by reading the full state from Redis on
  WebSocket re-authentication.
