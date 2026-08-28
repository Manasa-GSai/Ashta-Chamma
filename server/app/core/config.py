"""Application configuration loaded from environment variables."""

import os


class Settings:
    """Application settings, read once from environment at startup."""

    database_url: str = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/ashtachamma",
    )
    redis_url: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
    clerk_jwks_url: str = os.environ.get(
        "CLERK_JWKS_URL",
        "https://api.clerk.dev/.well-known/jwks.json",
    )

    # Room lifecycle
    # BR-5: rooms auto-close after 15 minutes of inactivity
    room_inactivity_timeout_seconds: int = 15 * 60
    room_expiry_check_interval_seconds: int = 60

    player_colors: list[str] = ["red", "green", "yellow", "blue"]
    room_code_length: int = 6
    room_code_max_attempts: int = 10


settings = Settings()
