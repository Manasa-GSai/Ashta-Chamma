"""Application configuration loaded from environment variables.

Values are resolved once at import time. A restart is required to pick up
changes in production — this is intentional for predictability.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Settings:
    """Configuration values resolved from environment variables at startup.

    Sentry DSN is optional: when absent (local development), ``sentry_sdk.init``
    is skipped entirely so no network calls are made to Sentry.
    The DSN must come from an environment variable — it must never be hardcoded.
    """

    sentry_dsn: str = field(default_factory=lambda: os.getenv("SENTRY_DSN", ""))
    sentry_environment: str = field(
        default_factory=lambda: os.getenv("SENTRY_ENVIRONMENT", "development")
    )
    sentry_traces_sample_rate: float = field(
        default_factory=lambda: float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    )


settings = Settings()
