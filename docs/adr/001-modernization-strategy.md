# ADR-001: Full Replatform — Pygame to 3D Web Application

**Status:** Accepted

**Date:** 2025-01-13

## Context

The existing Ashta Chamma implementation is a monolithic pygame desktop application
(`game.py`, `player.py`, `path.py`, `helper.py`). It has no networking, no persistence,
no user accounts, and only runs locally on a machine with Python and pygame installed.
This limits the player base to developers willing to clone a repository and install
dependencies.

Key problems with the legacy architecture:
- **No multiplayer**: the entire game loop is single-process, single-machine.
- **No persistence**: no score history, no user profiles, no ranking.
- **No accessibility**: requires Python 3 + pygame on the host; no web access.
- **No maintainability**: rendering, input handling, game logic, and AI are all
  colocated in a single `game.py` main loop.

Options evaluated:

| Option | Pros | Cons |
|---|---|---|
| Incremental pygame refactor | Minimal risk; familiar tech | Does not solve networking or distribution problems |
| Pygame + WebSocket server | Adds multiplayer | Still requires client install; no 3D |
| Full web replatform (chosen) | Browser-native; multiplayer; modern stack | Higher initial investment |

## Decision

We will perform a **full replatform** to a modern web-based 3D game:

- **Client**: React SPA with React Three Fiber (Three.js) for 3D rendering, Vite for
  bundling, TypeScript for type safety, Zustand for state management.
- **Backend**: FastAPI (Python 3.12) on AWS ECS Fargate, providing REST endpoints and
  WebSocket handlers. Server-authoritative game logic to prevent cheating.
- **Infrastructure**: AWS CDK (TypeScript) for infrastructure-as-code — VPC, ECS,
  RDS PostgreSQL, ElastiCache Redis, S3 + CloudFront.
- **Legacy reference**: The pygame files are preserved at the repository root as a
  game-rule reference until the new engine reaches feature parity.

The replatform is structured as a monorepo with `client/`, `server/`, `infra/`, and
`docs/` top-level directories.

## Consequences

### Positive

- Ashta Chamma becomes a browser-accessible game with no install required.
- Multiplayer support via WebSocket connections and Redis pub/sub fan-out.
- Persistent user profiles, score history, and leaderboards.
- Scalable compute: ECS Fargate auto-scales with player load.
- Clear separation of concerns between frontend, backend, and infrastructure.
- Team can use modern tooling (TypeScript, Pydantic v2, ruff, pytest).

### Negative

- Significantly higher initial complexity compared to extending pygame.
- Requires AWS account and CDK knowledge for deployment.
- Cloud costs for RDS, ElastiCache, ECS that were zero for the local app.
- Longer development timeline (estimated 13–15 weeks across 5 phases).

### Risks

- 3D performance on low-end mobile devices — mitigated by a 60 FPS / 2 MB model
  budget and responsive LOD.
- WebSocket connection reliability on flaky networks — mitigated by client-side
  exponential backoff reconnection with server-side state recovery.
- Game-rule fidelity loss during replatform — mitigated by keeping the legacy code
  as a canonical reference and writing 100 % unit test coverage on the state machine.
