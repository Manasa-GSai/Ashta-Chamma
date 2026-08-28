"""Unit tests for load-tests/websocket_load.py.

Tests cover:
  - JWT generation and decoding
  - WebSocket message helpers (build_message, parse_ws_message)
  - LatencyTracker: recording, percentiles, thread safety
  - RoomPool: add/next/is_ready
  - ScenarioConfig: validation errors
  - GameSession: connect failure path, error accumulation
  - measure_latency context manager

These tests run without a live server — all network calls are mocked.
"""

from __future__ import annotations

import json
import threading
import time
import uuid
from unittest.mock import MagicMock, patch

import jwt
import pytest

# ---------------------------------------------------------------------------
# Import the module under test.  We patch heavy optional imports at module
# load time so the test runner does not need locust or websocket-client
# installed in the default test environment.
# ---------------------------------------------------------------------------

import sys

# Provide lightweight stubs if the optional packages are absent so that the
# module can still be imported during unit tests in the base server environment.
if "locust" not in sys.modules:
    locust_stub = MagicMock()
    locust_stub.HttpUser = object  # base class used by AshtaChammaPlayer
    locust_stub.between = lambda _a, _b: (lambda self: None)
    locust_stub.events = MagicMock()
    locust_stub.task = lambda weight=1: (lambda f: f)  # identity decorator
    sys.modules["locust"] = locust_stub
    sys.modules["locust.env"] = MagicMock()

if "websocket" not in sys.modules:
    sys.modules["websocket"] = MagicMock()

from websocket_load import (  # noqa: E402 — must come after stub injection
    DEFAULT_SCENARIO,
    P95_LATENCY_SLO_MS,
    GameSession,
    LatencyTracker,
    RoomPool,
    ScenarioConfig,
    build_message,
    decode_test_jwt,
    generate_test_jwt,
    measure_latency,
    parse_ws_message,
)


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------


class TestGenerateTestJwt:
    def test_returns_string(self) -> None:
        token = generate_test_jwt("user-123")
        assert isinstance(token, str)
        assert len(token) > 10

    def test_contains_user_id(self) -> None:
        uid = str(uuid.uuid4())
        token = generate_test_jwt(uid)
        decoded = decode_test_jwt(token)
        assert decoded["sub"] == uid

    def test_includes_room_id_when_provided(self) -> None:
        uid = str(uuid.uuid4())
        rid = str(uuid.uuid4())
        token = generate_test_jwt(uid, room_id=rid)
        decoded = decode_test_jwt(token)
        assert decoded["room_id"] == rid

    def test_no_room_id_by_default(self) -> None:
        token = generate_test_jwt("user-abc")
        decoded = decode_test_jwt(token)
        assert "room_id" not in decoded

    def test_issuer_is_load_test(self) -> None:
        token = generate_test_jwt("user-xyz")
        decoded = decode_test_jwt(token)
        assert decoded["iss"] == "load-test"

    def test_expiry_is_in_the_future(self) -> None:
        token = generate_test_jwt("user-exp")
        decoded = decode_test_jwt(token)
        assert decoded["exp"] > int(time.time())

    def test_hs256_algorithm(self) -> None:
        token = generate_test_jwt("user-alg")
        header = jwt.get_unverified_header(token)
        assert header["alg"] == "HS256"


class TestDecodeTestJwt:
    def test_round_trip(self) -> None:
        uid = "roundtrip-user"
        token = generate_test_jwt(uid)
        payload = decode_test_jwt(token)
        assert payload["sub"] == uid

    def test_ignores_expiry(self) -> None:
        """decode_test_jwt should not raise on an already-expired token."""
        # Create a token that expired 1 second ago
        import time as _time

        now = int(_time.time())
        payload = {"sub": "old-user", "exp": now - 1, "iss": "load-test"}
        from load_tests.websocket_load import TEST_JWT_SECRET

        expired_token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        decoded = decode_test_jwt(expired_token)
        assert decoded["sub"] == "old-user"


# ---------------------------------------------------------------------------
# Message helpers
# ---------------------------------------------------------------------------


class TestBuildMessage:
    def test_type_field_present(self) -> None:
        raw = build_message("roll_request")
        data = json.loads(raw)
        assert data["type"] == "roll_request"

    def test_extra_kwargs_included(self) -> None:
        raw = build_message("select_pawn", pawn_id=2)
        data = json.loads(raw)
        assert data["pawn_id"] == 2

    def test_no_extra_kwargs(self) -> None:
        raw = build_message("ping")
        data = json.loads(raw)
        assert data == {"type": "ping"}

    def test_multiple_kwargs(self) -> None:
        raw = build_message("chat", text="hello", from_="player1")
        data = json.loads(raw)
        assert data["text"] == "hello"
        assert data["from_"] == "player1"


class TestParseWsMessage:
    def test_valid_json(self) -> None:
        msg = parse_ws_message('{"type": "pong"}')
        assert msg == {"type": "pong"}

    def test_invalid_json_returns_empty_dict(self) -> None:
        msg = parse_ws_message("not-json")
        assert msg == {}

    def test_empty_string_returns_empty_dict(self) -> None:
        msg = parse_ws_message("")
        assert msg == {}

    def test_nested_json(self) -> None:
        payload = json.dumps({"type": "state_update", "state": {"turn": 1}})
        msg = parse_ws_message(payload)
        assert msg["state"]["turn"] == 1


# ---------------------------------------------------------------------------
# LatencyTracker
# ---------------------------------------------------------------------------


class TestLatencyTracker:
    def test_record_and_sample_count(self) -> None:
        t = LatencyTracker()
        t.record("roll_result", 50.0)
        t.record("roll_result", 80.0)
        assert t.sample_count("roll_result") == 2

    def test_unknown_type_returns_zero_count(self) -> None:
        t = LatencyTracker()
        assert t.sample_count("nonexistent") == 0

    def test_percentiles_with_enough_samples(self) -> None:
        t = LatencyTracker()
        # Insert 100 samples 1..100 ms so quantiles are well-defined
        for i in range(1, 101):
            t.record("ping", float(i))
        pcts = t.percentiles("ping")
        assert pcts["p50"] == pytest.approx(50.0, abs=5.0)
        assert pcts["p95"] == pytest.approx(95.0, abs=5.0)
        assert pcts["p99"] == pytest.approx(99.0, abs=5.0)

    def test_percentiles_with_few_samples_returns_zeros(self) -> None:
        t = LatencyTracker()
        t.record("roll_result", 42.0)  # only 1 sample
        pcts = t.percentiles("roll_result")
        assert pcts == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_percentiles_unknown_type_returns_zeros(self) -> None:
        t = LatencyTracker()
        pcts = t.percentiles("nope")
        assert pcts == {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    def test_mean_latency(self) -> None:
        t = LatencyTracker()
        t.record("msg", 10.0)
        t.record("msg", 20.0)
        assert t.mean_latency("msg") == pytest.approx(15.0)

    def test_mean_latency_empty(self) -> None:
        t = LatencyTracker()
        assert t.mean_latency("missing") == 0.0

    def test_all_percentiles_keys(self) -> None:
        t = LatencyTracker()
        for i in range(1, 101):
            t.record("a", float(i))
            t.record("b", float(i))
        all_pcts = t.all_percentiles()
        assert "a" in all_pcts
        assert "b" in all_pcts

    def test_thread_safety(self) -> None:
        """Multiple threads recording concurrently must not corrupt state."""
        t = LatencyTracker()
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for i in range(100):
                    t.record("concurrent", float(i))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        assert not errors
        assert t.sample_count("concurrent") == 1000


# ---------------------------------------------------------------------------
# RoomPool
# ---------------------------------------------------------------------------


class TestRoomPool:
    def test_initially_empty(self) -> None:
        pool = RoomPool(capacity=10)
        assert pool.size() == 0
        assert not pool.is_ready()

    def test_add_and_size(self) -> None:
        pool = RoomPool()
        pool.add("room-1")
        assert pool.size() == 1
        assert pool.is_ready()

    def test_next_room_round_robin(self) -> None:
        pool = RoomPool()
        pool.add("a")
        pool.add("b")
        ids = [pool.next_room_id() for _ in range(4)]
        # Should cycle: a, b, a, b
        assert ids == ["a", "b", "a", "b"]

    def test_next_room_empty_returns_none(self) -> None:
        pool = RoomPool()
        assert pool.next_room_id() is None

    def test_thread_safe_add(self) -> None:
        pool = RoomPool()
        errors: list[Exception] = []

        def add_rooms() -> None:
            try:
                for i in range(50):
                    pool.add(f"room-{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=add_rooms) for _ in range(4)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        assert not errors
        assert pool.size() == 200


# ---------------------------------------------------------------------------
# ScenarioConfig
# ---------------------------------------------------------------------------


class TestScenarioConfig:
    def test_valid_default_scenario(self) -> None:
        errors = DEFAULT_SCENARIO.validate()
        assert errors == []

    def test_mismatched_users_rooms(self) -> None:
        cfg = ScenarioConfig(
            users=100,
            rooms=10,
            players_per_room=4,  # 10 × 4 = 40, not 100
            ramp_up_seconds=60,
            sustain_seconds=300,
            ramp_down_seconds=30,
            p95_slo_ms=150.0,
        )
        errors = cfg.validate()
        assert any("users" in e for e in errors)

    def test_zero_rooms_error(self) -> None:
        cfg = ScenarioConfig(
            users=0,
            rooms=0,
            players_per_room=4,
            ramp_up_seconds=60,
            sustain_seconds=300,
            ramp_down_seconds=30,
            p95_slo_ms=150.0,
        )
        errors = cfg.validate()
        assert len(errors) >= 2  # users=0, rooms=0

    def test_negative_slo_error(self) -> None:
        cfg = ScenarioConfig(
            users=4,
            rooms=1,
            players_per_room=4,
            ramp_up_seconds=60,
            sustain_seconds=300,
            ramp_down_seconds=30,
            p95_slo_ms=-1.0,
        )
        errors = cfg.validate()
        assert any("p95_slo_ms" in e for e in errors)

    def test_perfect_match_no_errors(self) -> None:
        cfg = ScenarioConfig(
            users=500,
            rooms=125,
            players_per_room=4,
            ramp_up_seconds=120,
            sustain_seconds=300,
            ramp_down_seconds=60,
            p95_slo_ms=150.0,
        )
        assert cfg.validate() == []


# ---------------------------------------------------------------------------
# GameSession (mocked WebSocket)
# ---------------------------------------------------------------------------


class TestGameSession:
    def _make_session(self) -> GameSession:
        return GameSession(
            ws_base_url="ws://localhost:8000",
            room_id="room-abc",
            user_id="user-xyz",
            token=generate_test_jwt("user-xyz", "room-abc"),
        )

    def test_connect_failure_sets_not_connected(self) -> None:
        session = self._make_session()
        with patch("load_tests.websocket_load.websocket") as mock_ws:
            mock_ws.create_connection.side_effect = ConnectionRefusedError("refused")
            result = session.connect()
        assert not result
        assert not session.connected
        assert any("connect error" in e for e in session.errors)

    def test_disconnect_is_idempotent(self) -> None:
        session = self._make_session()
        session.disconnect()  # should not raise even with no live connection
        session.disconnect()  # second call also safe

    def test_send_roll_request_without_connection_returns_negative(self) -> None:
        session = self._make_session()
        # session is not connected
        latency = session.send_roll_request()
        assert latency == -1.0

    def test_send_select_pawn_without_connection_returns_negative(self) -> None:
        session = self._make_session()
        latency = session.send_select_pawn()
        assert latency == -1.0

    def test_send_ping_without_connection_returns_negative(self) -> None:
        session = self._make_session()
        latency = session.send_ping()
        assert latency == -1.0

    def test_parse_ws_message_handles_malformed_data(self) -> None:
        session = self._make_session()
        session.connected = True
        result = parse_ws_message("{bad json}")
        assert result == {}


# ---------------------------------------------------------------------------
# measure_latency context manager
# ---------------------------------------------------------------------------


class TestMeasureLatency:
    def test_records_positive_latency(self) -> None:
        tracker = LatencyTracker()
        with measure_latency("test_op", tracker=tracker):
            time.sleep(0.005)  # 5 ms
        assert tracker.sample_count("test_op") == 1
        assert tracker.mean_latency("test_op") > 0

    def test_records_even_on_exception(self) -> None:
        tracker = LatencyTracker()
        with pytest.raises(ValueError):  # noqa: PT011
            with measure_latency("error_op", tracker=tracker):
                raise ValueError("test error")
        # Latency is still recorded in the finally block
        assert tracker.sample_count("error_op") == 1


# ---------------------------------------------------------------------------
# SLO constant sanity check
# ---------------------------------------------------------------------------


def test_p95_slo_constant() -> None:
    """The SLO constant must match the PRD requirement of < 150 ms."""
    assert P95_LATENCY_SLO_MS == 150.0
