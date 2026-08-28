"""Domain enumerations shared across models and services."""

import enum


class RoomStatus(str, enum.Enum):
    """Lifecycle states of a game room in PostgreSQL."""

    WAITING = "waiting"
    PLAYING = "playing"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DifficultyLevel(str, enum.Enum):
    """AI persona difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"
