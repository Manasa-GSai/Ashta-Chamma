"""Smoke test for the server package scaffold.

This verifies the `app` package imports cleanly and exposes the expected
version constant. Subsequent work orders will add real test coverage for
routers, services, and game logic.
"""

from app import __version__


def test_version_is_set() -> None:
    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_version_is_semver_like() -> None:
    parts = __version__.split(".")
    assert len(parts) >= 2
    assert all(part.isdigit() for part in parts[:2])
