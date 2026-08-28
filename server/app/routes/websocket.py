"""WebSocket endpoint for real-time Ashta Chamma game communication.

Endpoint: ``wss://host/ws/rooms/{room_id}?token={jwt}``

Connection lifecycle
--------------------
1. JWT validated from ``?token=`` query param — close 4001 on failure.
2. ``websocket.accept()`` called only after successful auth.
3. Reconnection check: if the player has a disconnection record in Redis
   (within the 60-second window), the full game state is sent immediately.
4. Redis pub/sub listener started as a background ``asyncio.Task``.
5. Message loop: receive text, enforce 1 KB limit, parse/validate JSON,
   route by ``type`` field.
6. On disconnect: background task cancelled, player marked as disconnected
   in Redis with a 60-second TTL (reconnection window).

Fan-out strategy
----------------
All game-state broadcasts go through Redis pub/sub on channel
``room:{room_id}``.  The Redis listener task on every ECS instance that
has connections to that room forwards received messages to those WebSockets.
This ensures correct behaviour under horizontal scaling (AC-5).

Security constraints
--------------------
- JWT validated once on connection, not per message (constraint §2).
- Game actions validated server-side (constraint §3).
- Never trust the client — all roll and move results come from server logic.
- Messages rejected after schema validation failure, not silently ignored.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, WebSocketException

from app.dependencies.auth import ws_authenticate
from app.providers.redis import get_redis
from app.repositories.audit_log import write_audit_log
from app.schemas.websocket import (
    MAX_MESSAGE_BYTES,
    ErrorMessage,
    GameStateUpdateMessage,
    PingMessage,
    PongMessage,
    RollRequestMessage,
    RollResultMessage,
    SelectPawnMessage,
    StateUpdateMessage,
    parse_client_message,
)
from app.services.connection_manager import manager as connection_manager
from app.services.game_session import GameSession

router = APIRouter(tags=["websocket"])

_logger = logging.getLogger(__name__)

# Redis key prefix for disconnected-player records used in reconnect logic.
_DISCONNECT_KEY_PREFIX: str = "disconnected"
# How long (seconds) to keep a disconnection record so reconnects restore state.
_RECONNECT_WINDOW_SECONDS: int = 60


@router.websocket("/ws/rooms/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
    token: str = Query(default=""),
) -> None:
    """Real-time WebSocket handler for a single game room.

    Authentication is performed before ``accept()`` by catching the
    ``WebSocketException`` and closing with the appropriate code, which
    causes Starlette to perform a reject-on-upgrade internally.
    """
    # ------------------------------------------------------------------
    # Step 1: Authenticate.  Close 4001 before accepting on failure.
    # ------------------------------------------------------------------
    try:
        claims = ws_authenticate(token)
    except WebSocketException:
        await websocket.close(code=4001)
        return

    player_id: str = claims.get("sub", "") or claims.get("user_id", "")
    if not player_id:
        await websocket.close(code=4001)
        return

    # ------------------------------------------------------------------
    # Step 2: Accept connection and register with the in-process manager.
    # ------------------------------------------------------------------
    await websocket.accept()
    connection_manager.register(room_id, player_id, websocket)

    redis = await get_redis()
    game_session = GameSession(room_id=room_id, redis=redis)

    # ------------------------------------------------------------------
    # Step 3: Reconnection check — send full state if within window.
    # ------------------------------------------------------------------
    disconnect_key = f"{_DISCONNECT_KEY_PREFIX}:{room_id}:{player_id}"
    was_disconnected: int = await redis.exists(disconnect_key)
    if was_disconnected:
        await redis.delete(disconnect_key)
        full_state = await game_session.get_state()
        await websocket.send_json(StateUpdateMessage(state=full_state).model_dump())
        _logger.info(
            "Player %s reconnected to room %s; full state sent", player_id, room_id
        )

    # ------------------------------------------------------------------
    # Step 4: Start Redis pub/sub listener (cross-instance fan-out).
    # ------------------------------------------------------------------
    listener_task: asyncio.Task[None] = asyncio.create_task(
        _redis_pubsub_listener(room_id, player_id, websocket),
        name=f"redis-listener:{room_id}:{player_id}",
    )

    try:
        # --------------------------------------------------------------
        # Step 5: Message loop.
        # --------------------------------------------------------------
        while True:
            raw: str = await websocket.receive_text()

            # Enforce 1 KB per-message limit (OWASP / constraint §6).
            if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
                await websocket.send_json(
                    ErrorMessage(message="Message exceeds maximum allowed size").model_dump()
                )
                continue

            # Parse JSON.
            try:
                data: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json(ErrorMessage(message="Invalid JSON").model_dump())
                continue

            # Validate against schema.
            try:
                msg = parse_client_message(data)
            except Exception:
                await websocket.send_json(
                    ErrorMessage(message="Unknown or invalid message type").model_dump()
                )
                continue

            await _dispatch(
                msg=msg,
                room_id=room_id,
                player_id=player_id,
                websocket=websocket,
                game_session=game_session,
                redis=redis,
            )

    except WebSocketDisconnect:
        _logger.info("Player %s disconnected from room %s", player_id, room_id)
    finally:
        # ------------------------------------------------------------------
        # Step 6: Clean up — cancel listener, deregister, mark disconnected.
        # ------------------------------------------------------------------
        listener_task.cancel()
        connection_manager.deregister(room_id, player_id, websocket)

        # Preserve a disconnection record so reconnects within 60 s restore state.
        await redis.setex(disconnect_key, _RECONNECT_WINDOW_SECONDS, "1")
        _logger.info(
            "Player %s marked disconnected in room %s (TTL=%ds)",
            player_id,
            room_id,
            _RECONNECT_WINDOW_SECONDS,
        )


# ---------------------------------------------------------------------------
# Message dispatch
# ---------------------------------------------------------------------------


async def _dispatch(
    msg: RollRequestMessage | SelectPawnMessage | PingMessage,
    room_id: str,
    player_id: str,
    websocket: WebSocket,
    game_session: GameSession,
    redis: Any,
) -> None:
    """Route a validated client message to the appropriate handler."""
    # Ping is handled directly — no turn validation required.
    if isinstance(msg, PingMessage):
        await websocket.send_json(PongMessage().model_dump())
        return

    # All game actions require it to be the player's turn.
    current_player = await game_session.get_current_player()
    # When no current player is set (game not yet started / state not initialised)
    # we allow the action so the first roll can kick things off.
    if current_player and current_player != player_id:
        await websocket.send_json(
            ErrorMessage(message="Not your turn").model_dump()
        )
        return

    if isinstance(msg, RollRequestMessage):
        await _handle_roll_request(
            room_id=room_id,
            player_id=player_id,
            game_session=game_session,
            redis=redis,
        )
    elif isinstance(msg, SelectPawnMessage):
        await _handle_select_pawn(
            room_id=room_id,
            player_id=player_id,
            pawn_id=msg.pawn_id,
            game_session=game_session,
            redis=redis,
        )


# ---------------------------------------------------------------------------
# Game action handlers
# ---------------------------------------------------------------------------


async def _handle_roll_request(
    room_id: str,
    player_id: str,
    game_session: GameSession,
    redis: Any,
) -> None:
    """Execute a cowrie roll and publish the result to all room members.

    The result is published to Redis pub/sub so every ECS instance forwards
    it to their locally-connected clients (AC-5 fan-out requirement).
    """
    result = await game_session.roll(player_id)

    roll_msg = RollResultMessage(
        value=result["value"],
        shells=result["shells"],
        player_id=result["player_id"],
    )
    channel = f"room:{room_id}"
    await redis.publish(channel, json.dumps(roll_msg.model_dump()))

    # Audit trail (AC-8).
    await write_audit_log(
        actor_id=player_id,
        action="game.roll",
        entity_type="room",
        entity_id=room_id,
        metadata={"value": result["value"]},
    )


async def _handle_select_pawn(
    room_id: str,
    player_id: str,
    pawn_id: int,
    game_session: GameSession,
    redis: Any,
) -> None:
    """Execute a pawn selection/move and broadcast the state delta.

    The state delta is published to Redis pub/sub (AC-5 fan-out requirement).
    """
    state_delta = await game_session.select_pawn(player_id, pawn_id)

    update_msg = GameStateUpdateMessage(state_delta=state_delta)
    channel = f"room:{room_id}"
    await redis.publish(channel, json.dumps(update_msg.model_dump()))

    # Audit trail (AC-8).
    await write_audit_log(
        actor_id=player_id,
        action="game.move",
        entity_type="room",
        entity_id=room_id,
        metadata={"pawn_id": pawn_id},
    )


# ---------------------------------------------------------------------------
# Redis pub/sub listener (background task)
# ---------------------------------------------------------------------------


async def _redis_pubsub_listener(
    room_id: str,
    player_id: str,
    websocket: WebSocket,
) -> None:
    """Subscribe to ``room:{room_id}`` and forward messages to *websocket*.

    Runs as an ``asyncio.Task`` for the lifetime of the WebSocket connection.
    A dedicated ``pubsub()`` object is used because once subscribed, a Redis
    connection can only issue subscribe/unsubscribe commands — it cannot be
    shared with regular commands.

    On ``CancelledError`` (raised when the connection closes), the subscription
    is cleaned up gracefully.
    """
    from app.providers.redis import get_redis as _get_redis

    redis = await _get_redis()
    pubsub = redis.pubsub()
    channel = f"room:{room_id}"
    await pubsub.subscribe(channel)
    _logger.debug(
        "Redis pub/sub listener started for room=%s player=%s", room_id, player_id
    )

    try:
        async for raw_msg in pubsub.listen():
            # ``listen()`` yields subscribe-confirmation messages first.
            if raw_msg.get("type") != "message":
                continue
            try:
                payload: dict[str, Any] = json.loads(raw_msg["data"])
                await websocket.send_json(payload)
            except WebSocketDisconnect:
                # The WebSocket closed mid-send; stop listening.
                break
            except Exception:
                _logger.exception(
                    "Error forwarding pub/sub message to player %s in room %s",
                    player_id,
                    room_id,
                )
    except asyncio.CancelledError:
        pass  # Task cancelled on disconnect — expected path
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()
        _logger.debug(
            "Redis pub/sub listener stopped for room=%s player=%s", room_id, player_id
        )
