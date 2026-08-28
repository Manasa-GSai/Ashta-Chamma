"""
Locust load test for Ashta Chamma WebSocket server.

Scenario: 500 concurrent WebSocket connections across 125 rooms (4 players each).
Each simulated player performs: connect, authenticate, roll, select pawn — in a loop.

Measures:
  - WebSocket message round-trip latency (p50, p95, p99)
  - Connection success rate
  - Error rate

Run against staging only — never production.

Usage:
    locust -f load-tests/websocket_load.py \
        --host http://staging.example.com \
        --users 500 \
        --spawn-rate 10 \
        --run-time 7m \
        --headless \
        --html load-tests/results/report.html \
        --csv load-tests/results/metrics

Environment variables:
    TARGET_HOST       Base URL of the staging server (overrides --host)
    TEST_JWT_SECRET   HS256 secret for generating test JWTs (default: test-secret)
    ROOMS_COUNT       Number of rooms to pre-create (default: 125)
    PLAYERS_PER_ROOM  Players per room (default: 4)
    MAX_CONNECTIONS   Stop-test threshold — p95 latency violation threshold tracking (default: 500)
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from statistics import mean, quantiles
from typing import Any

import jwt  # PyJWT
import websocket  # websocket-client
from locust import HttpUser, between, events, task
from locust.env import Environment

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TEST_JWT_SECRET: str = os.environ.get("TEST_JWT_SECRET", "test-secret-do-not-use-in-production")
ROOMS_COUNT: int = int(os.environ.get("ROOMS_COUNT", "125"))
PLAYERS_PER_ROOM: int = int(os.environ.get("PLAYERS_PER_ROOM", "4"))
# p95 SLO target in milliseconds
P95_LATENCY_SLO_MS: float = 150.0
# Threshold to flag a latency measurement as a violation
SLOW_THRESHOLD_MS: float = 150.0

logger = logging.getLogger("websocket_load")


# ---------------------------------------------------------------------------
# JWT generation helpers
# ---------------------------------------------------------------------------


def generate_test_jwt(user_id: str, room_id: str | None = None) -> str:
    """Generate a HS256-signed test JWT for load test sessions.

    Real JWTs are Clerk RS256 tokens; this uses a shared HS256 secret that
    the staging server must be configured to accept via the TEST_AUTH_BYPASS
    environment variable.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "iat": now,
        "exp": now + 3600,  # 1-hour TTL — sufficient for a load test run
        "iss": "load-test",
    }
    if room_id is not None:
        payload["room_id"] = room_id
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def decode_test_jwt(token: str) -> dict[str, Any]:
    """Decode a test JWT, ignoring expiry (for test utilities only)."""
    return jwt.decode(
        token,
        TEST_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_exp": False},
    )


# ---------------------------------------------------------------------------
# WebSocket message helpers
# ---------------------------------------------------------------------------


def build_message(msg_type: str, **kwargs: Any) -> str:
    """Serialize a client-to-server WebSocket message as JSON."""
    return json.dumps({"type": msg_type, **kwargs})


def parse_ws_message(raw: str) -> dict[str, Any]:
    """Parse a raw WebSocket JSON message into a dict.

    Returns an empty dict on malformed input rather than propagating the
    parse error — the caller should treat this as an unexpected message type.
    """
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse WebSocket message: %r", raw)
        return {}


# ---------------------------------------------------------------------------
# Latency tracker — thread-safe rolling window
# ---------------------------------------------------------------------------


@dataclass
class LatencyTracker:
    """Thread-safe store of per-message-type latency samples (in milliseconds)."""

    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _samples: dict[str, list[float]] = field(default_factory=dict, repr=False)

    def record(self, message_type: str, latency_ms: float) -> None:
        with self._lock:
            self._samples.setdefault(message_type, []).append(latency_ms)

    def percentiles(self, message_type: str) -> dict[str, float]:
        """Return p50 / p95 / p99 for *message_type*.

        Returns zeros when fewer than two samples exist (quantiles() needs ≥ 2).
        """
        with self._lock:
            samples = list(self._samples.get(message_type, []))
        if len(samples) < 2:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        qs = quantiles(samples, n=100)
        return {
            "p50": qs[49],
            "p95": qs[94],
            "p99": qs[98],
        }

    def all_percentiles(self) -> dict[str, dict[str, float]]:
        with self._lock:
            types_ = list(self._samples.keys())
        return {t: self.percentiles(t) for t in types_}

    def sample_count(self, message_type: str) -> int:
        with self._lock:
            return len(self._samples.get(message_type, []))

    def mean_latency(self, message_type: str) -> float:
        with self._lock:
            samples = list(self._samples.get(message_type, []))
        return mean(samples) if samples else 0.0


# Global tracker shared across all Locust workers in-process
_latency_tracker = LatencyTracker()


# ---------------------------------------------------------------------------
# Room pool — shared state for distributing users across rooms
# ---------------------------------------------------------------------------


class RoomPool:
    """Thread-safe pool for assigning users to rooms (4 players per room).

    Rooms are created via the REST API before users start sending WebSocket
    messages.  Players cycle through rooms so each room keeps approximately
    PLAYERS_PER_ROOM concurrent connections.
    """

    def __init__(self, capacity: int = ROOMS_COUNT) -> None:
        self._lock = threading.Lock()
        self._rooms: list[str] = []  # list of room IDs
        self._capacity = capacity
        self._index = 0  # round-robin index

    def add(self, room_id: str) -> None:
        with self._lock:
            self._rooms.append(room_id)

    def next_room_id(self) -> str | None:
        """Return the next room ID in round-robin order, or None if pool is empty."""
        with self._lock:
            if not self._rooms:
                return None
            room_id = self._rooms[self._index % len(self._rooms)]
            self._index += 1
            return room_id

    def size(self) -> int:
        with self._lock:
            return len(self._rooms)

    def is_ready(self) -> bool:
        """Return True once at least one room has been created."""
        return self.size() > 0


# Global room pool
_room_pool = RoomPool()


# ---------------------------------------------------------------------------
# Scenario configuration validation
# ---------------------------------------------------------------------------


@dataclass
class ScenarioConfig:
    """Validated load test configuration."""

    users: int
    rooms: int
    players_per_room: int
    ramp_up_seconds: int
    sustain_seconds: int
    ramp_down_seconds: int
    p95_slo_ms: float

    def validate(self) -> list[str]:
        """Return a list of validation error strings, empty if config is valid."""
        errors: list[str] = []
        if self.users <= 0:
            errors.append(f"users must be > 0, got {self.users}")
        if self.rooms <= 0:
            errors.append(f"rooms must be > 0, got {self.rooms}")
        if self.players_per_room <= 0:
            errors.append(f"players_per_room must be > 0, got {self.players_per_room}")
        if self.p95_slo_ms <= 0:
            errors.append(f"p95_slo_ms must be > 0, got {self.p95_slo_ms}")
        expected_users = self.rooms * self.players_per_room
        if self.users != expected_users:
            errors.append(
                f"users ({self.users}) should equal rooms × players_per_room "
                f"({self.rooms} × {self.players_per_room} = {expected_users})"
            )
        return errors


DEFAULT_SCENARIO = ScenarioConfig(
    users=500,
    rooms=125,
    players_per_room=4,
    ramp_up_seconds=120,   # 2-minute ramp up (0 → 500)
    sustain_seconds=300,   # 5-minute sustain
    ramp_down_seconds=60,  # 1-minute ramp down
    p95_slo_ms=P95_LATENCY_SLO_MS,
)


# ---------------------------------------------------------------------------
# Context manager: measure round-trip latency
# ---------------------------------------------------------------------------


@contextmanager
def measure_latency(
    message_type: str,
    tracker: LatencyTracker = _latency_tracker,
) -> Iterator[None]:
    """Context manager that records wall-clock latency for a send→receive pair."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        tracker.record(message_type, elapsed_ms)


# ---------------------------------------------------------------------------
# WebSocket game session
# ---------------------------------------------------------------------------


class GameSession:
    """Synchronous WebSocket session representing one player in a room.

    Connects to the server, authenticates via JWT query parameter, then runs
    the game loop: roll → wait for roll_result → select pawn → wait for
    state_update.  Latencies are recorded in *_latency_tracker*.
    """

    # Time to wait for a server response before treating it as a timeout (seconds)
    RECV_TIMEOUT: float = 5.0
    # Maximum messages to drain looking for a specific response type
    MAX_DRAIN: int = 20

    def __init__(
        self,
        ws_base_url: str,
        room_id: str,
        user_id: str,
        token: str,
    ) -> None:
        self.ws_base_url = ws_base_url
        self.room_id = room_id
        self.user_id = user_id
        self.token = token
        self._ws: websocket.WebSocket | None = None
        self.connected = False
        self.errors: list[str] = []

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """Open the WebSocket connection.  Returns True on success."""
        url = f"{self.ws_base_url}/ws/rooms/{self.room_id}?token={self.token}"
        try:
            self._ws = websocket.create_connection(
                url,
                timeout=self.RECV_TIMEOUT,
                # Suppress verbose websocket-client logs
                suppress_origin=True,
            )
            self.connected = True
            # Drain the initial state_update sent by the server on join
            self._drain_until("state_update", timeout=self.RECV_TIMEOUT)
            return True
        except Exception as exc:
            self.errors.append(f"connect error: {exc}")
            self.connected = False
            return False

    def disconnect(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
        self.connected = False

    # ------------------------------------------------------------------
    # Game loop actions
    # ------------------------------------------------------------------

    def send_roll_request(self) -> float:
        """Send roll_request and wait for roll_result.

        Returns round-trip latency in milliseconds, or -1 on failure.
        """
        if not self._ws or not self.connected:
            return -1.0
        start = time.perf_counter()
        try:
            self._ws.send(build_message("roll_request"))
            _msg = self._drain_until("roll_result", timeout=self.RECV_TIMEOUT)
            latency_ms = (time.perf_counter() - start) * 1000.0
            if _msg:
                _latency_tracker.record("roll_result", latency_ms)
                return latency_ms
            else:
                self.errors.append("roll_result not received within timeout")
                return -1.0
        except Exception as exc:
            self.errors.append(f"roll_request error: {exc}")
            return -1.0

    def send_select_pawn(self, pawn_id: int = 0) -> float:
        """Send select_pawn and wait for state_update.

        Returns round-trip latency in milliseconds, or -1 on failure.
        """
        if not self._ws or not self.connected:
            return -1.0
        start = time.perf_counter()
        try:
            self._ws.send(build_message("select_pawn", pawn_id=pawn_id))
            _msg = self._drain_until("state_update", timeout=self.RECV_TIMEOUT)
            latency_ms = (time.perf_counter() - start) * 1000.0
            if _msg:
                _latency_tracker.record("state_update", latency_ms)
                return latency_ms
            else:
                self.errors.append("state_update not received after select_pawn")
                return -1.0
        except Exception as exc:
            self.errors.append(f"select_pawn error: {exc}")
            return -1.0

    def send_ping(self) -> float:
        """Send ping and wait for pong.  Returns RTT in ms or -1."""
        if not self._ws or not self.connected:
            return -1.0
        start = time.perf_counter()
        try:
            self._ws.send(build_message("ping"))
            _msg = self._drain_until("pong", timeout=self.RECV_TIMEOUT)
            latency_ms = (time.perf_counter() - start) * 1000.0
            if _msg:
                _latency_tracker.record("pong", latency_ms)
                return latency_ms
            else:
                self.errors.append("pong not received within timeout")
                return -1.0
        except Exception as exc:
            self.errors.append(f"ping error: {exc}")
            return -1.0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _drain_until(
        self,
        target_type: str,
        timeout: float = RECV_TIMEOUT,
    ) -> dict[str, Any] | None:
        """Receive messages until *target_type* is found or timeout expires."""
        if not self._ws:
            return None
        deadline = time.perf_counter() + timeout
        for _ in range(self.MAX_DRAIN):
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                break
            try:
                self._ws.settimeout(min(remaining, 1.0))
                raw = self._ws.recv()
                msg = parse_ws_message(raw)
                if msg.get("type") == target_type:
                    return msg
            except websocket.WebSocketTimeoutException:
                break
            except Exception as exc:
                self.errors.append(f"recv error: {exc}")
                break
        return None


# ---------------------------------------------------------------------------
# Locust user
# ---------------------------------------------------------------------------


class AshtaChammaPlayer(HttpUser):
    """Simulates a single player: creates/joins a room, then loops over game actions.

    Spawn rate and user count are controlled by the Locust CLI / config.
    For 500 concurrent connections across 125 rooms, run with:
        --users 500 --spawn-rate 10
    """

    # Think time between game loop iterations (seconds)
    wait_time = between(0.1, 0.5)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session: GameSession | None = None
        self._user_id: str = str(uuid.uuid4())
        self._room_id: str | None = None
        self._token: str = generate_test_jwt(self._user_id)
        self._loop_count: int = 0

    # ------------------------------------------------------------------
    # Setup / teardown
    # ------------------------------------------------------------------

    def on_start(self) -> None:
        """Called once per simulated user at spawn time."""
        self._room_id = self._get_or_create_room()
        if self._room_id is None:
            logger.error("User %s: could not obtain a room — skipping", self._user_id)
            return
        ws_url = self._http_to_ws_url(self.host)
        self._session = GameSession(
            ws_base_url=ws_url,
            room_id=self._room_id,
            user_id=self._user_id,
            token=self._token,
        )
        success = self._session.connect()
        if success:
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="connect",
                response_time=0,
                response_length=0,
                exception=None,
                context={},
            )
        else:
            err = "; ".join(self._session.errors)
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="connect",
                response_time=0,
                response_length=0,
                exception=ConnectionError(err),
                context={},
            )

    def on_stop(self) -> None:
        if self._session:
            self._session.disconnect()

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @task(weight=1)
    def game_loop(self) -> None:
        """One iteration of the game loop: roll → select pawn."""
        if self._session is None or not self._session.connected:
            return

        # --- Roll ---
        roll_latency = self._session.send_roll_request()
        if roll_latency >= 0:
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="roll_request→roll_result",
                response_time=roll_latency,
                response_length=0,
                exception=None,
                context={},
            )
        else:
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="roll_request→roll_result",
                response_time=0,
                response_length=0,
                exception=TimeoutError("roll_result not received"),
                context={},
            )

        # --- Select pawn ---
        select_latency = self._session.send_select_pawn(pawn_id=self._loop_count % 4)
        if select_latency >= 0:
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="select_pawn→state_update",
                response_time=select_latency,
                response_length=0,
                exception=None,
                context={},
            )
        else:
            self.environment.events.request.fire(
                request_type="WebSocket",
                name="select_pawn→state_update",
                response_time=0,
                response_length=0,
                exception=TimeoutError("state_update not received"),
                context={},
            )

        self._loop_count += 1

    @task(weight=1)
    def ping_pong(self) -> None:
        """Send a ping and record keep-alive latency."""
        if self._session is None or not self._session.connected:
            return
        latency = self._session.send_ping()
        self.environment.events.request.fire(
            request_type="WebSocket",
            name="ping→pong",
            response_time=latency if latency >= 0 else 0,
            response_length=0,
            exception=None if latency >= 0 else TimeoutError("pong not received"),
            context={},
        )

    # ------------------------------------------------------------------
    # Room creation helper
    # ------------------------------------------------------------------

    def _get_or_create_room(self) -> str | None:
        """Return an existing room ID from the pool or create a new one via REST."""
        if _room_pool.is_ready():
            return _room_pool.next_room_id()

        # Be the first user to create rooms (others will wait for the pool to fill)
        with _creation_lock:
            if _room_pool.is_ready():
                return _room_pool.next_room_id()
            # Create rooms up to ROOMS_COUNT
            rooms_needed = ROOMS_COUNT - _room_pool.size()
            for _ in range(rooms_needed):
                room_id = self._create_room_via_rest()
                if room_id:
                    _room_pool.add(room_id)

        return _room_pool.next_room_id()

    def _create_room_via_rest(self) -> str | None:
        """POST /api/rooms and return the new room ID."""
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            with self.client.post(
                "/api/rooms",
                json={"max_players": PLAYERS_PER_ROOM},
                headers=headers,
                name="/api/rooms [setup]",
                catch_response=True,
            ) as resp:
                if resp.status_code in (200, 201):
                    data = resp.json()
                    room_id = data.get("room_id") or data.get("id")
                    if room_id:
                        resp.success()
                        return str(room_id)
                    resp.failure(f"No room_id in response: {data}")
                else:
                    resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
        except Exception as exc:
            logger.error("Failed to create room: %s", exc)
        return None

    @staticmethod
    def _http_to_ws_url(http_url: str) -> str:
        """Convert http(s):// to ws(s):// for WebSocket connections."""
        return http_url.replace("https://", "wss://").replace("http://", "ws://")


# Lock used when first populating the room pool
_creation_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Event hooks — print SLO summary on test completion
# ---------------------------------------------------------------------------


@events.quitting.add_listener
def _on_quitting(environment: Environment, **_kwargs: Any) -> None:
    """Print a summary of WebSocket latency percentiles and SLO pass/fail status."""
    stats = _latency_tracker.all_percentiles()
    if not stats:
        logger.info("No WebSocket latency samples collected.")
        return

    print("\n" + "=" * 60)
    print("  WEBSOCKET LATENCY SLO REPORT")
    print("=" * 60)
    slo_pass = True
    for msg_type, pcts in stats.items():
        p95 = pcts["p95"]
        status = "✓ PASS" if p95 < P95_LATENCY_SLO_MS else "✗ FAIL"
        if p95 >= P95_LATENCY_SLO_MS:
            slo_pass = False
        n = _latency_tracker.sample_count(msg_type)
        avg = _latency_tracker.mean_latency(msg_type)
        print(
            f"  {msg_type:<35} n={n:<6} "
            f"mean={avg:>7.1f}ms  "
            f"p50={pcts['p50']:>7.1f}ms  "
            f"p95={p95:>7.1f}ms  "
            f"p99={pcts['p99']:>7.1f}ms  {status}"
        )
    print("=" * 60)
    slo_label = "ALL SLOs PASSED" if slo_pass else "ONE OR MORE SLOs FAILED"
    print(f"  {slo_label}  (SLO: p95 < {P95_LATENCY_SLO_MS}ms)")
    print("=" * 60 + "\n")


@events.test_start.add_listener
def _on_test_start(environment: Environment, **_kwargs: Any) -> None:
    logger.info(
        "Load test started — target: %d users, %d rooms × %d players",
        DEFAULT_SCENARIO.users,
        DEFAULT_SCENARIO.rooms,
        DEFAULT_SCENARIO.players_per_room,
    )
    logger.info(
        "Scenario: ramp-up %ds, sustain %ds, ramp-down %ds",
        DEFAULT_SCENARIO.ramp_up_seconds,
        DEFAULT_SCENARIO.sustain_seconds,
        DEFAULT_SCENARIO.ramp_down_seconds,
    )
    logger.info("SLO: p95 WebSocket latency < %.0f ms", DEFAULT_SCENARIO.p95_slo_ms)
