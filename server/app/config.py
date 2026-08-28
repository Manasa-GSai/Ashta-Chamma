"""Application configuration loaded from environment variables.

All configurable values are read at module import time so that they can be
overridden in tests by patching ``os.environ`` before importing the module.
"""

import os

DATABASE_URL: str = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/ashta_chamma",
)
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")

# BR-5: rooms idle for longer than this many seconds are auto-closed.
ROOM_IDLE_TIMEOUT_SECONDS: int = int(os.environ.get("ROOM_IDLE_TIMEOUT_SECONDS", "900"))

# How often (in seconds) the background cleanup task runs.
CLEANUP_INTERVAL_SECONDS: int = int(os.environ.get("CLEANUP_INTERVAL_SECONDS", "60"))
