"""Pydantic schemas for the WebSocket message protocol.

All messages carry a ``type`` discriminator field that routes them to the
appropriate handler.  Client-to-server messages are parsed and validated
before any game logic runs (OWASP input validation).

Message size is capped at 1 KB (``MAX_MESSAGE_BYTES``) — enforced in the
WebSocket route handler before JSON parsing.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

MAX_MESSAGE_BYTES: int = 1024  # 1 KB per-message limit


# ---------------------------------------------------------------------------
# Client → Server messages
# ---------------------------------------------------------------------------


class RollRequestMessage(BaseModel):
    """Client requests a cowrie roll for the current turn."""

    type: Literal["roll_request"] = "roll_request"


class SelectPawnMessage(BaseModel):
    """Client selects a pawn to move after viewing legal-move options."""

    type: Literal["select_pawn"] = "select_pawn"
    pawn_id: int = Field(..., ge=0, le=15)  # 4 players × 4 pawns max


class PingMessage(BaseModel):
    """Keep-alive ping from client."""

    type: Literal["ping"] = "ping"


# Discriminated union — Pydantic routes on the ``type`` literal
ClientMessage = Annotated[
    Union[RollRequestMessage, SelectPawnMessage, PingMessage],
    Field(discriminator="type"),
]

_client_adapter: TypeAdapter[RollRequestMessage | SelectPawnMessage | PingMessage] | None = None


def parse_client_message(
    data: dict[str, Any],
) -> RollRequestMessage | SelectPawnMessage | PingMessage:
    """Validate and parse a raw dict into the correct client message type.

    Raises ``pydantic.ValidationError`` if the payload does not match any
    known message schema.  The route handler converts this to an error reply.
    """
    global _client_adapter
    if _client_adapter is None:
        _client_adapter = TypeAdapter(ClientMessage)  # type: ignore[assignment]
    return _client_adapter.validate_python(data)


# ---------------------------------------------------------------------------
# Server → Client messages
# ---------------------------------------------------------------------------


class RollResultMessage(BaseModel):
    """Cowrie roll outcome — broadcast to all room members after a roll."""

    type: Literal["roll_result"] = "roll_result"
    value: int
    shells: list[bool]  # True = face-up for each of the 4 cowries
    player_id: str


class GameStateUpdateMessage(BaseModel):
    """Incremental state delta broadcast after a pawn move."""

    type: Literal["game_state_update"] = "game_state_update"
    state_delta: dict[str, Any]


class StateUpdateMessage(BaseModel):
    """Full game state sent to a reconnecting client."""

    type: Literal["state_update"] = "state_update"
    state: dict[str, Any]


class ErrorMessage(BaseModel):
    """Error notification sent to the originating client only."""

    type: Literal["error"] = "error"
    message: str


class PongMessage(BaseModel):
    """Keep-alive pong in response to a client ping."""

    type: Literal["pong"] = "pong"


class PlayerJoinedMessage(BaseModel):
    """Broadcast when a player joins or reconnects to a room."""

    type: Literal["player_joined"] = "player_joined"
    player_id: str
    display_name: str


class PlayerLeftMessage(BaseModel):
    """Broadcast when a player disconnects from a room."""

    type: Literal["player_left"] = "player_left"
    player_id: str
