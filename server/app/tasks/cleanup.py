"""Idle-room cleanup background task.

Business rule BR-5: room sessions that have been inactive for more than
``ROOM_IDLE_TIMEOUT_SECONDS`` (default: 900 s / 15 min) are automatically
transitioned to ``abandoned`` status with appropriate cleanup.

Algorithm (single pass)
-----------------------
1. Scan Redis for all ``room:*:last_activity`` keys.
2. For each key, read the Unix timestamp value.
3. If ``now - last_activity > ROOM_IDLE_TIMEOUT_SECONDS``:
   a. Broadcast ``{type: "room_closed", reason: "inactivity"}`` to WebSocket clients.
   b. Update the room row in PostgreSQL: ``status = abandoned``, ``ended_at = now``.
   c. Append an ``audit_logs`` entry with ``action = "room.auto_closed"``.
   d. Delete ephemeral Redis keys for the room.
4. Rooms already in a terminal state (``completed``, ``abandoned``) are skipped
   — the operation is idempotent.

The loop is registered via FastAPI's lifespan context and runs every
``CLEANUP_INTERVAL_SECONDS`` (default: 60 s) without blocking the event loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from sqlalchemy import select

from app.config import CLEANUP_INTERVAL_SECONDS, ROOM_IDLE_TIMEOUT_SECONDS
from app.db import AsyncSessionLocal
from app.models.room import AuditLog, Room, RoomStatus
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

# Redis key pattern used to discover all active rooms.
_LAST_ACTIVITY_PATTERN: str = "room:*:last_activity"

# Suffixes of Redis keys to delete when a room is abandoned.
_REDIS_KEY_SUFFIXES: tuple[str, ...] = ("state", "players", "chat", "last_activity")


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------


def _parse_room_id_from_key(key: str) -> str | None:
    """Extract the room_id from a ``room:{room_id}:last_activity`` key.

    Returns ``None`` for any key that does not match the expected pattern.
    """
    parts = key.split(":")
    if len(parts) == 3 and parts[0] == "room" and parts[2] == "last_activity":
        return parts[1]
    return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_cleanup_loop() -> None:
    """Run ``cleanup_idle_rooms`` every ``CLEANUP_INTERVAL_SECONDS`` seconds.

    This coroutine is started as a non-blocking ``asyncio.Task`` in the
    application lifespan.  It catches all unhandled exceptions to prevent
    the loop from dying silently; each failure is logged before sleeping.
    """
    logger.info(
        "Idle-room cleanup task started (interval=%ds, idle_timeout=%ds).",
        CLEANUP_INTERVAL_SECONDS,
        ROOM_IDLE_TIMEOUT_SECONDS,
    )
    while True:
        try:
            await cleanup_idle_rooms()
        except Exception:  # noqa: BLE001
            logger.exception("Unhandled error in cleanup_idle_rooms.")
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


# ---------------------------------------------------------------------------
# Single-pass cleanup
# ---------------------------------------------------------------------------


async def cleanup_idle_rooms() -> None:
    """Perform one cleanup pass: find and abandon all currently idle rooms.

    Redis errors during the scan phase cause the entire pass to abort early
    (logged as a warning).  Errors for individual rooms are caught per-room
    so that one bad room cannot block the rest.
    """
    redis_client = get_redis()
    now = int(time.time())

    try:
        keys: list[str] = await redis_client.keys(_LAST_ACTIVITY_PATTERN)
    except aioredis.RedisError as exc:
        logger.warning("Redis unavailable during idle-room scan: %s", exc)
        return

    for key in keys:
        room_id = _parse_room_id_from_key(key)
        if room_id is None:
            logger.debug("Skipping unexpected key: %r", key)
            continue

        try:
            raw_ts: str | None = await redis_client.get(key)
        except aioredis.RedisError as exc:
            logger.warning("Redis error reading last_activity for room %s: %s", room_id, exc)
            continue

        if raw_ts is None:
            # Key expired between the KEYS scan and the GET — treat as gone.
            continue

        try:
            last_activity = int(raw_ts)
        except ValueError:
            logger.warning(
                "Malformed last_activity value for room %s: %r — skipping.", room_id, raw_ts
            )
            continue

        idle_seconds = now - last_activity
        if idle_seconds <= ROOM_IDLE_TIMEOUT_SECONDS:
            continue  # Room is still active

        logger.info(
            "Room %s idle for %d s — initiating abandonment.", room_id, idle_seconds
        )
        try:
            await _abandon_room(room_id, redis_client)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to abandon room %s.", room_id)


# ---------------------------------------------------------------------------
# Per-room abandonment
# ---------------------------------------------------------------------------


async def _abandon_room(room_id: str, redis_client: aioredis.Redis) -> None:  # type: ignore[type-arg]
    """Perform the full abandonment sequence for a single idle room.

    Steps are ordered so that clients are notified before state is wiped,
    and the PostgreSQL update is committed before Redis keys are deleted.
    If the room is already in a terminal state the function exits early
    without touching Redis — ensuring idempotency.
    """
    # 1. Notify connected WebSocket clients before any state is removed.
    await _notify_clients(room_id)

    # 2. Persist the status change.  Returns False if already terminal.
    updated = await _persist_abandoned_status(room_id)
    if not updated:
        logger.debug("Room %s already in terminal state; skipping Redis cleanup.", room_id)
        return

    # 3. Remove ephemeral Redis keys only after a successful DB commit.
    await _delete_redis_keys(room_id, redis_client)


async def _notify_clients(room_id: str) -> None:
    """Broadcast ``room_closed`` to every WebSocket connection in the room.

    The import is deferred to avoid a circular dependency: cleanup.py imports
    from routes.websocket, which would otherwise create an import cycle at
    module load time if done at the top level.
    """
    # Deferred import to break the circular dependency with routes.websocket.
    from app.routes.websocket import broadcast_to_room  # noqa: PLC0415

    try:
        await broadcast_to_room(room_id, {"type": "room_closed", "reason": "inactivity"})
    except Exception:  # noqa: BLE001
        # Notification failure must not abort the cleanup sequence.
        logger.warning("Failed to notify clients in room %s.", room_id)


async def _persist_abandoned_status(room_id: str) -> bool:
    """Transition the room to ``abandoned`` in PostgreSQL and write an audit log.

    Returns
    -------
    ``True``  — the room was successfully updated.
    ``False`` — the room was already in a terminal state or was not found;
                Redis cleanup should be skipped to preserve idempotency.
    """
    try:
        room_uuid = uuid.UUID(room_id)
    except ValueError:
        logger.warning("Skipping room with non-UUID id: %r", room_id)
        return False

    ended_at = datetime.now(timezone.utc)
    terminal_statuses = (RoomStatus.COMPLETED, RoomStatus.ABANDONED)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(select(Room).where(Room.id == room_uuid))
            room = result.scalar_one_or_none()

            if room is None:
                logger.warning("Room %s not found in PostgreSQL; skipping.", room_id)
                return False

            if room.status in terminal_statuses:
                logger.debug(
                    "Room %s already has terminal status %s.", room_id, room.status
                )
                return False

            # Transition to abandoned.
            room.status = RoomStatus.ABANDONED
            room.ended_at = ended_at

            # Append immutable audit trail entry.
            session.add(
                AuditLog(
                    actor_id=None,  # system-initiated action
                    action="room.auto_closed",
                    entity_type="room",
                    entity_id=str(room_uuid),
                    metadata={
                        "reason": "inactivity",
                        "ended_at": ended_at.isoformat(),
                    },
                )
            )

    return True


async def _delete_redis_keys(
    room_id: str, redis_client: aioredis.Redis  # type: ignore[type-arg]
) -> None:
    """Delete all ephemeral Redis keys associated with the room.

    Keys deleted: ``room:{id}:state``, ``room:{id}:players``,
    ``room:{id}:chat``, ``room:{id}:last_activity``.

    Redis errors are caught and logged; the cleanup sequence continues.
    """
    keys = [f"room:{room_id}:{suffix}" for suffix in _REDIS_KEY_SUFFIXES]
    try:
        await redis_client.delete(*keys)
    except aioredis.RedisError as exc:
        logger.warning("Redis error while deleting keys for room %s: %s", room_id, exc)
