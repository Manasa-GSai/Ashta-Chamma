"""Shared SQLAlchemy declarative base.

All ORM models import from here to share the same MetaData instance,
which is required for Alembic autogenerate to detect all tables and for
relationship resolution across modules.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Project-wide SQLAlchemy declarative base."""
