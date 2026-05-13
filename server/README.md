# Ashta Chamma 3D — Server

FastAPI backend for the Ashta Chamma 3D board game.

## Stack

- Python 3.12+
- FastAPI + Uvicorn (async ASGI)
- Pydantic v2 (request/response validation)
- SQLAlchemy 2.0 async (PostgreSQL persistence)
- Poetry (dependency management)
- Ruff (lint + format), Mypy (type checking), Pytest (tests)

## Quickstart

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run linting
ruff check .

# Run tests
pytest

# Start the dev server (added in a later work order)
# uvicorn app.main:app --reload
```

## Layout

```
server/
├── app/         # FastAPI application package
└── tests/       # Pytest suite
```

Subsequent work orders will add the FastAPI app skeleton (WO-004), Clerk JWT
middleware (WO-008), game state machine (WO-013), WebSocket handlers (WO-016),
and database models (WO-005).
