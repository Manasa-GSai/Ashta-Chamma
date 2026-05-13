# Ashta Chamma 3D

A web-based 3D modernization of the traditional Indian board game **Ashta Chamma**
(aka *Daayam*, *Tabla*) — built on **React Three Fiber + FastAPI + PostgreSQL**
and deployed to **AWS**. See [Ashta Chamma on Wikipedia](https://wiki2.org/en/Ashta_Chamma_(board_game))
for background on the game itself.

This repository is a monorepo containing both the browser client and the
server-authoritative game backend. The legacy pygame implementation
(`game.py`, `player.py`, `path.py`, `helper.py`) is preserved at the repo
root as a rule-fidelity reference until the new engine reaches feature parity.

## Monorepo layout

```
.
├── client/         # React + TypeScript + Vite SPA (React Three Fiber)
│   ├── src/
│   └── public/
├── server/         # FastAPI + Pydantic v2 backend (Poetry / uv)
│   ├── app/
│   └── tests/
├── infra/          # AWS CDK stacks (VPC, ECS, RDS, Redis, S3/CloudFront)
├── docs/           # Architecture, API, runbooks, game-rule specs
└── (legacy)        # game.py / player.py / path.py / helper.py (reference)
```

## Quickstart

### Client (Vite + React + TypeScript)

```bash
cd client
npm install
npm run build      # produces dist/
npm run lint
npm run dev        # local dev server at http://localhost:5173
```

TypeScript is configured with `"strict": true` and `"noImplicitAny": true`.
Linting uses **ESLint 9 (flat config)** + `typescript-eslint`, with Prettier
for formatting.

### Server (FastAPI + Poetry)

```bash
cd server
poetry install     # or: uv sync
ruff check .
pytest
```

Python **3.12+** is required. Core dependencies pinned in `server/pyproject.toml`:
FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.0 (async).

## What this work order delivers

This is **WO-001 — Initialize Monorepo with Build Tooling** (REQ-016, AWS
Infrastructure Deployment). It establishes the directory layout, build
toolchain, and lint/format/type-check baseline for both client and server.
Application code, CDK stacks, and CI/CD are intentionally out of scope and
are tracked under WO-002 (CDK), WO-003 (GitHub Actions), and WO-004 (FastAPI
skeleton).

## License

See `LICENSE`. Originally authored by
[Jaya Shankar](https://github.com/jaya-shankar) and
[InputBlackBoxOutput](https://github.com/InputBlackBoxOutput); modernization
in progress.
