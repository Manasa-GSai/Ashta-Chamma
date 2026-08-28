"""Pydantic models for WebSocket message validation.

All client-to-server WebSocket messages must conform to one of the schemas
defined here.  The ``validate_ws_message`` function is the single entry point
used by the WebSocket handler to parse and validate raw JSON strings.

Strict mode is enabled on every model so that, for example, a string "1"
is never silently coerced to the integer 1 for ``pawn_id``.  This prevents
subtle bugs and closes a class of injection vectors.
"""

import json
from typing import Annotated, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError


class _StrictBase(BaseModel):
    """Base model with strict type coercion disabled for all WS schemas."""

    model_config = ConfigDict(strict=True)


# ---------------------------------------------------------------------------
# Client → Server message types
# ---------------------------------------------------------------------------


class RollRequestMessage(_StrictBase):
    """Player requests a cowrie throw."""

    type: Annotated[str, Field()] = "roll_request"


class SelectPawnMessage(_StrictBase):
    """Player selects a pawn to move after seeing move options."""

    type: Annotated[str, Field()] = "select_pawn"
    pawn_id: int


class ChatMessage(_StrictBase):
    """Player sends an in-game chat message."""

    type: Annotated[str, Field()] = "chat"
    text: str = Field(..., min_length=1, max_length=500)


class PingMessage(_StrictBase):
    """Keep-alive ping from the client."""

    type: Annotated[str, Field()] = "ping"


# ---------------------------------------------------------------------------
# Server → Client message types
# ---------------------------------------------------------------------------


class ErrorMessage(BaseModel):
    """Server sends this when a client message fails validation or auth."""

    type: str = "error"
    message: str


# ---------------------------------------------------------------------------
# Discriminated union & validator
# ---------------------------------------------------------------------------

# All valid client message types keyed by the ``type`` literal discriminator.
ClientMessage = Annotated[
    Union[RollRequestMessage, SelectPawnMessage, ChatMessage, PingMessage],
    Field(discriminator="type"),
]

# Build once at module load; reusing TypeAdapter avoids per-call schema rebuild.
_CLIENT_MESSAGE_ADAPTER: TypeAdapter[  # type: ignore[type-arg]
    RollRequestMessage | SelectPawnMessage | ChatMessage | PingMessage
] = TypeAdapter(ClientMessage)


def validate_ws_message(
    raw: str,
) -> RollRequestMessage | SelectPawnMessage | ChatMessage | PingMessage:
    """Parse and validate a raw JSON WebSocket message.

    Args:
        raw: The raw JSON string received from the WebSocket client.

    Returns:
        A typed message model matching the ``type`` discriminator.

    Raises:
        ValueError: If the payload is not valid JSON or does not conform to
            any of the defined message schemas.  Internal Pydantic error
            details are intentionally omitted from the raised message to
            prevent leaking server internals to clients.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Invalid JSON payload") from exc

    try:
        return _CLIENT_MESSAGE_ADAPTER.validate_python(data)
    except ValidationError as exc:
        # Re-raise with a generic message; callers send "Invalid message format"
        # to the client rather than Pydantic's detailed error list.
        raise ValueError("Message does not match any known schema") from exc
