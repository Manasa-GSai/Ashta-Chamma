"""Pydantic schemas for user profile endpoints.

``UserResponse`` is the outbound representation of a user record.  It
intentionally excludes internal columns (``updated_at``) and exposes only
the safe profile data the frontend needs.

``UserUpdateRequest`` validates profile mutations with strict types and
length limits.  The ``display_name`` validator also strips HTML tags to
mitigate stored-XSS attacks before the value is persisted.
"""

import re
import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_html(value: str) -> str:
    """Remove all HTML tags from *value* using a simple regex.

    We do not rely on an external sanitisation library (e.g. ``bleach``) so
    that the security boundary stays in pure-stdlib code that is easy to
    audit.  The regex ``<[^>]*>`` matches every tag including attributes.
    """
    return re.sub(r"<[^>]*>", "", value)


class UserResponse(BaseModel):
    """Safe, public representation of a user profile returned by the API."""

    # from_attributes allows Pydantic to read fields from SQLAlchemy ORM
    # instances directly (replaces orm_mode from Pydantic v1).
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clerk_id: str
    display_name: str
    avatar_url: str | None
    locale: str
    created_at: datetime


class UserUpdateRequest(BaseModel):
    """Validated payload for PUT /api/users/me.

    ``strict=True`` disables Pydantic's implicit type coercion so that, for
    example, an integer locale value is rejected rather than silently cast
    to a string.  This prevents clients from accidentally sending the wrong
    type and receiving a 200 OK.
    """

    model_config = ConfigDict(strict=True)

    display_name: Annotated[str, Field(min_length=1, max_length=100)]
    locale: Literal["en", "te"]

    @field_validator("display_name")
    @classmethod
    def sanitize_display_name(cls, v: str) -> str:
        """Strip HTML tags and re-validate minimum length after stripping."""
        sanitised = _strip_html(v).strip()
        if len(sanitised) < 1:
            raise ValueError(
                "display_name must contain at least one non-tag character"
            )
        return sanitised
