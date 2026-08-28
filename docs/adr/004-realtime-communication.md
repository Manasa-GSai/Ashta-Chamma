# ADR-004: Real-Time Communication — WebSocket with Redis Pub/Sub

**Status:** Accepted

**Date:** 2025-01-27

## Context

Ashta Chamma is a turn-based multiplayer game where up to 4 players (human or AI)
share a single board. Every game event — cowrie rolls, pawn moves, captures — must
be broadcast to all participants in near-real-time. The communication layer must:

- Deliver game state updates to all room members with < 100 ms p95 latency.
- Work across multiple ECS Fargate task instances (horizontal scaling).
- Handle player disconnects and reconnects gracefully.
- Support both game events and in-game chat.

Options evaluated:

| Option | Pros | Cons |
|---|---|---|
| HTTP polling | Simple; stateless | High latency; wasteful; poor UX for turn-based games |
| Server-Sent Events (SSE) | Simple server push; works with proxies | Unidirectional only; clients cannot send events back |
| **WebSocket + Redis pub/sub** (chosen) | Bidirectional; low latency; scales across tasks | More complex; requires connection management |
| WebRTC data channels | Peer-to-peer; very low latency | Complex signaling; not suited for server-authoritative model |

## Decision

We will use **persistent WebSocket connections** for all in-game communication,
with **Redis pub/sub** as the fan-out layer across multiple ECS Fargate tasks.

**Architecture:**

```
Client A ←WSS→ Fargate Task 1 → Redis pub/sub channel (room:{id})
Client B ←WSS→ Fargate Task 2 ←  Redis pub/sub channel (room:{id})
Client C ←WSS→ Fargate Task 1 ←  (same channel, shared)
```

- Each Fargate task maintains a local registry of WebSocket connections.
- When the game FSM emits a state update, it publishes to a Redis channel
  named `room:{room_id}`.
- Every Fargate task subscribed to that channel receives the message and
  forwards it to any locally-connected clients in that room.
- The REST API (`POST /api/rooms`, `GET /api/rooms/{code}`) handles non-real-time
  CRUD operations.

**WebSocket endpoint:** `wss://api.example.com/ws/rooms/{room_id}?token={jwt}`

All messages are JSON with a `type` discriminator field (see
`docs/architecture.md` for the full message catalogue).

**Connection lifecycle:**
1. Client upgrades HTTP to WSS, passing JWT as query param.
2. Server validates JWT via Clerk JWKS, rejects with 4001 on failure.
3. Server subscribes to `room:{room_id}` Redis channel.
4. Server sends an initial `state_update` snapshot to the newly connected client.
5. Client sends `ping` every 30 s; server responds with `pong` to detect dead connections.
6. On disconnect, server unsubscribes if no other local clients remain in the room.

## Consequences

### Positive

- Bidirectional low-latency communication suits the turn-based game UX.
- Redis pub/sub decouples the Fargate tasks; any task can handle any client.
- Horizontal scaling: adding Fargate tasks requires no code changes.
- Standard WebSocket protocol is well-supported in all modern browsers and the
  ALB (sticky sessions not required because state lives in Redis).

### Negative

- Persistent connections consume server resources; a limit of 400 concurrent
  connections (100 rooms × 4 players) is the initial target.
- ALB WebSocket idle timeout (60 s default) must be raised to 3600 s to avoid
  spurious disconnects during long games.
- Redis is now on the critical path; full Redis failure degrades all real-time
  communication across multi-task deployments.

### Risks

- **Message ordering**: Redis pub/sub does not guarantee ordering across multiple
  publishers. For a turn-based game where only the current player publishes
  during their turn, this is not a practical concern. A sequence number is
  included as a safety net.
- **Redis failover gap**: ElastiCache Redis failover takes 20–30 seconds.
  During that window, pub/sub is unavailable. Single-task deployments can
  continue in-memory; multi-task fan-out is degraded.
  Mitigation: ECS circuit breaker rolls back bad deployments; staging validates
  Redis connectivity before production promotion.
