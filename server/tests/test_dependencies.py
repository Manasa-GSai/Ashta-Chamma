"""Tests for app/dependencies.py.

Covers:
- get_current_user_id exists and is callable.
- get_current_clerk_id alias resolves to the same function object.
  (The alias was added to fix an ImportError that crashed the container on
  startup — app/routes/users.py imports get_current_clerk_id while the
  implementation was only named get_current_user_id.)
"""


def test_get_current_user_id_importable() -> None:
    """get_current_user_id can be imported from app.dependencies."""
    from app.dependencies import get_current_user_id  # noqa: PLC0415

    assert callable(get_current_user_id)


def test_get_current_clerk_id_alias_importable() -> None:
    """get_current_clerk_id alias can be imported from app.dependencies."""
    from app.dependencies import get_current_clerk_id  # noqa: PLC0415

    assert callable(get_current_clerk_id)


def test_clerk_id_alias_is_same_object_as_user_id() -> None:
    """get_current_clerk_id and get_current_user_id are the same function.

    This ensures the alias does not silently diverge from the implementation
    in future refactors.
    """
    from app.dependencies import get_current_clerk_id, get_current_user_id  # noqa: PLC0415

    assert get_current_clerk_id is get_current_user_id
