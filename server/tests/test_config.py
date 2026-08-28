"""Unit tests for application configuration.

Covers env-var resolution, defaults, and type coercion so that
misconfigured deployments surface clearly at startup rather than
at runtime.
"""

import os
from unittest.mock import patch


def _make_settings(**overrides: str) -> "Settings":  # type: ignore[name-defined]
    """Reload Settings with a clean environment containing only the given vars."""
    import importlib

    with patch.dict(os.environ, overrides, clear=True):
        import app.config as cfg_module

        importlib.reload(cfg_module)
        return cfg_module.Settings()


def test_sentry_dsn_defaults_to_empty_string() -> None:
    from app.config import Settings

    s = Settings()
    with patch.dict(os.environ, {}, clear=True):
        assert Settings().sentry_dsn == ""


def test_sentry_dsn_reads_from_env() -> None:
    from app.config import Settings

    with patch.dict(os.environ, {"SENTRY_DSN": "https://abc@sentry.io/1"}):
        assert Settings().sentry_dsn == "https://abc@sentry.io/1"


def test_sentry_environment_defaults_to_development() -> None:
    from app.config import Settings

    with patch.dict(os.environ, {}, clear=True):
        assert Settings().sentry_environment == "development"


def test_sentry_environment_reads_from_env() -> None:
    from app.config import Settings

    with patch.dict(os.environ, {"SENTRY_ENVIRONMENT": "production"}):
        assert Settings().sentry_environment == "production"


def test_traces_sample_rate_defaults_to_0_1() -> None:
    from app.config import Settings

    with patch.dict(os.environ, {}, clear=True):
        assert Settings().sentry_traces_sample_rate == 0.1


def test_traces_sample_rate_reads_from_env() -> None:
    from app.config import Settings

    with patch.dict(os.environ, {"SENTRY_TRACES_SAMPLE_RATE": "0.5"}):
        assert Settings().sentry_traces_sample_rate == 0.5
