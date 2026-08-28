"""Custom exceptions for the Ashta Chamma game engine.

All game-logic errors derive from GameError so callers can catch a single
base class.  InvalidActionError is the primary error type that WebSocket
handlers translate into client-visible error messages.
"""


class GameError(Exception):
    """Base class for all game-engine errors."""


class InvalidActionError(GameError):
    """Raised when a client attempts an action that violates the FSM rules.

    Examples:
        - Rolling when the state is not ROLLING.
        - Selecting a pawn that is not in the current legal-move list.
        - Selecting a pawn owned by a player other than the active player.
    """


class InvalidStateTransitionError(GameError):
    """Raised when an internal state transition is attempted illegally.

    This guards against programming errors inside the state machine itself
    rather than client mistakes.
    """
