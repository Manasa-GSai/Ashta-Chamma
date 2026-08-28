"""Shared declarative base for all SQLAlchemy ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Common base class inherited by every ORM model in this package."""
