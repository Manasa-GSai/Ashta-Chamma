"""Sentry context helpers for WebSocket error capture.

WebSocket handlers should use ``websocket_sentry_context`` to enrich Sentry
events with ``room_id`` so errors can be triaged per game room without
needing to search through logs.

Usage::

    async def handle_ws_message(websocket: WebSocket, room_id: str, user_id: str) -> None:
        with websocket_sentry_context(room_id=room_id, user_id=user_id):
            data = await websocket.receive_json()
            await dispatch(data)
"""

from collections.abc import Generator
from contextlib import contextmanager

import sentry_sdk


@contextmanager
def websocket_sentry_context(
    room_id: str,
    user_id: str | None = None,
) -> Generator[None, None, None]:
    """Attach room and user context to Sentry events inside a WebSocket handler.

    Opens a new Sentry scope, sets ``room_id`` as a searchable tag, and
    optionally sets the user to the authenticated ``user_id``.  Only the
    user ID is attached — PII such as email and display name must not be sent.

    Exceptions raised inside the ``with`` block are captured and then
    re-raised so the caller's error handling remains unaffected.
    """
    with sentry_sdk.new_scope() as scope:
        scope.set_tag("room_id", room_id)
        if user_id is not None:
            # Only send user ID — never PII like email or display_name.
            scope.set_user({"id": user_id})
        try:
            yield
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            raise
