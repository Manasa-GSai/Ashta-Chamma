"""GameSession — server-authoritative game state for Ashta Chamma.

GameSession is the in-memory representation of a live game. It is
serialised to JSON and stored in Redis keyed by room_id so that any
Fargate task can access the current state without a DB round-trip.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.game.board import HOME_POSITIONS, PAWNS_PER_PLAYER


class GameState(str, Enum):
    """Finite states of the server-side Ashta Chamma state machine."""

    WAITING = "WAITING"
    ROLLING = "ROLLING"
    SELECTING = "SELECTING"
    MOVING = "MOVING"
    GAME_OVER = "GAME_OVER"


@dataclass
class PawnState:
    """Position and status of a single pawn."""

    pawn_id: int  # 0–3 within a player's set
    player_index: int  # 0–3 global player slot
    color: str  # matches PLAYER_COLORS
    position: tuple[int, int]  # (row, col) on the 9×9 grid
    is_home: bool = True  # True = at home base, not yet on the track
    is_finished: bool = False  # True = reached the goal square

    def to_dict(self) -> dict[str, Any]:
        return {
            "pawn_id": self.pawn_id,
            "player_index": self.player_index,
            "color": self.color,
            "position": list(self.position),
            "is_home": self.is_home,
            "is_finished": self.is_finished,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PawnState":
        return cls(
            pawn_id=data["pawn_id"],
            player_index=data["player_index"],
            color=data["color"],
            position=tuple(data["position"]),  # type: ignore[arg-type]
            is_home=data["is_home"],
            is_finished=data["is_finished"],
        )


@dataclass
class PlayerInfo:
    """Metadata for one player slot in the session."""

    player_index: int
    color: str
    user_id: str | None = None  # None for AI players
    ai_persona_id: int | None = None  # None for human players
    display_name: str = ""
    is_ai: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_index": self.player_index,
            "color": self.color,
            "user_id": self.user_id,
            "ai_persona_id": self.ai_persona_id,
            "display_name": self.display_name,
            "is_ai": self.is_ai,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlayerInfo":
        return cls(
            player_index=data["player_index"],
            color=data["color"],
            user_id=data.get("user_id"),
            ai_persona_id=data.get("ai_persona_id"),
            display_name=data.get("display_name", ""),
            is_ai=data.get("is_ai", False),
        )


@dataclass
class GameSession:
    """Full in-memory game state for one Ashta Chamma room.

    Creating a new GameSession with a player list automatically places all
    pawns at their home positions and sets the state to ROLLING so that
    the first player can act immediately.
    """

    room_id: str
    players: list[PlayerInfo]
    pawns: list[PawnState] = field(default_factory=list)
    state: GameState = GameState.ROLLING
    current_player_index: int = 0
    turn_number: int = 0

    def __post_init__(self) -> None:
        # Only initialise pawns when none are provided (new session).
        # Deserialisaton passes pre-built pawns, so we skip re-init there.
        if not self.pawns:
            self._initialize_pawns()

    # ------------------------------------------------------------------
    # Pawn initialisation
    # ------------------------------------------------------------------

    def _initialize_pawns(self) -> None:
        """Place all pawns at their respective home positions."""
        self.pawns = []
        for player in self.players:
            home_pos = HOME_POSITIONS[player.color]
            for pawn_id in range(PAWNS_PER_PLAYER):
                self.pawns.append(
                    PawnState(
                        pawn_id=pawn_id,
                        player_index=player.player_index,
                        color=player.color,
                        position=home_pos,
                        is_home=True,
                        is_finished=False,
                    )
                )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "players": [p.to_dict() for p in self.players],
            "pawns": [pw.to_dict() for pw in self.pawns],
            "state": self.state.value,
            "current_player_index": self.current_player_index,
            "turn_number": self.turn_number,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameSession":
        players = [PlayerInfo.from_dict(p) for p in data["players"]]
        pawns = [PawnState.from_dict(pw) for pw in data["pawns"]]
        # Use __new__ to skip __post_init__ auto-init since pawns are provided.
        session = cls.__new__(cls)
        session.room_id = data["room_id"]
        session.players = players
        session.pawns = pawns
        session.state = GameState(data["state"])
        session.current_player_index = data["current_player_index"]
        session.turn_number = data["turn_number"]
        return session

    @classmethod
    def from_json(cls, json_str: str) -> "GameSession":
        return cls.from_dict(json.loads(json_str))
