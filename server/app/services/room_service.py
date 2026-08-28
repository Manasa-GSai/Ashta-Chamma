"""Room management service.

Manages room state using an in-memory store that mirrors the Redis schema
described in the architecture. The interface is intentionally thin so the
backing store can be swapped for Redis without changing call sites.

Redis key mapping (for future reference):
  room:{code}            -> Hash of room metadata
  room:{code}:players    -> List of player dicts
  room:{code}:spectators -> Set of spectator user IDs
"""

from typing import Any

# ---------------------------------------------------------------------------
# In-memory backing store (simulates Redis for development / testing)
# ---------------------------------------------------------------------------

_rooms: dict[str, dict[str, Any]] = {}
_room_players: dict[str, list[dict[str, Any]]] = {}
_room_spectators: dict[str, set[str]] = {}

_PLAYER_COLORS = ["red", "green", "blue", "yellow"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_room(code: str, host_user_id: str, max_players: int = 4) -> dict[str, Any]:
    """Create a new room and seed its player/spectator lists."""
    room: dict[str, Any] = {
        "code": code,
        "host_user_id": host_user_id,
        "status": "waiting",
        "max_players": max_players,
    }
    _rooms[code] = room
    _room_players[code] = []
    _room_spectators[code] = set()
    return room


def get_room(code: str) -> dict[str, Any] | None:
    """Return room metadata or None if the code is unknown."""
    return _rooms.get(code)


def join_room(
    code: str,
    user_id: str,
    display_name: str,
) -> dict[str, Any] | None:
    """Add a user to a room as a player.

    Returns the player dict on success, or None when the room is full or
    the user is already tracked (as a player or spectator).
    """
    room = get_room(code)
    if room is None:
        return None

    players = _room_players.get(code, [])

    # Count only actual players (not spectators) against the limit
    actual_players = [p for p in players if p["role"] == "player"]
    if len(actual_players) >= room["max_players"]:
        return None  # Room is full

    player_index = len(actual_players)
    player: dict[str, Any] = {
        "user_id": user_id,
        "display_name": display_name,
        "role": "player",
        "player_index": player_index,
        "color": _PLAYER_COLORS[player_index % len(_PLAYER_COLORS)],
    }
    players.append(player)
    _room_players[code] = players
    return player


def spectate_room(
    code: str,
    user_id: str,
    display_name: str,
) -> dict[str, Any] | None:
    """Add a user to a room as a spectator.

    Spectators:
      - Do not count toward max_players.
      - Cannot perform game actions (enforced at the WebSocket layer).
      - Receive all pub/sub broadcasts identical to regular players.

    Returns the spectate response dict on success, or None when the room
    does not exist or the user is already a player in the room.
    """
    room = get_room(code)
    if room is None:
        return None

    # Users who are already playing cannot also spectate
    players = _room_players.get(code, [])
    if any(p["user_id"] == user_id and p["role"] == "player" for p in players):
        return None

    # Idempotent: if already spectating, return success without duplication
    spectators = _room_spectators.setdefault(code, set())
    if user_id not in spectators:
        spectators.add(user_id)
        players.append(
            {
                "user_id": user_id,
                "display_name": display_name,
                "role": "spectator",
                "player_index": None,
                "color": None,
            }
        )
        _room_players[code] = players

    return {
        "room_code": code,
        "user_id": user_id,
        "message": f"Now spectating room {code}",
    }


def is_spectator(code: str, user_id: str) -> bool:
    """Return True if the user is a registered spectator for this room."""
    return user_id in _room_spectators.get(code, set())


def get_room_players(code: str) -> list[dict[str, Any]]:
    """Return all tracked members of a room (players + spectators)."""
    return list(_room_players.get(code, []))


def clear_all() -> None:
    """Reset all in-memory state.  Intended for use in tests only."""
    _rooms.clear()
    _room_players.clear()
    _room_spectators.clear()
