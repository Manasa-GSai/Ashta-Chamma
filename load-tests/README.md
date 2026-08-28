# Ashta Chamma — WebSocket Load Tests

Load tests for the Ashta Chamma 3D WebSocket server.  These tests validate
that the system meets its SLOs under expected load before each release.

> **Important:** Load tests must run against **staging only** — never production.

---

## SLOs Under Test

| Metric | Target |
|---|---|
| WebSocket p95 round-trip latency | < 150 ms |
| WebSocket connection success rate | > 99% |
| Concurrent WebSocket connections | 500 (125 rooms × 4 players) |

---

## Scenario

| Phase | Duration | Connections |
|---|---|---|
| Ramp-up | 2 minutes | 0 → 500 |
| Sustain | 5 minutes | 500 (steady) |
| Ramp-down | 1 minute | 500 → 0 |

Each simulated player:
1. Creates or joins a room via `POST /api/rooms`
2. Upgrades to WebSocket at `wss://<host>/ws/rooms/{room_id}?token=<jwt>`
3. Loops: sends `roll_request` → waits for `roll_result` → sends `select_pawn`
   → waits for `state_update`

---

## Prerequisites

```bash
pip install -r load-tests/requirements.txt
```

---

## Configuration

| Environment Variable | Default | Description |
|---|---|---|
| `TARGET_HOST` | (none — required) | Staging base URL, e.g. `https://staging.example.com` |
| `TEST_JWT_SECRET` | `test-secret-do-not-use-in-production` | HS256 secret shared with the staging server |
| `ROOMS_COUNT` | `125` | Number of rooms to pre-create |
| `PLAYERS_PER_ROOM` | `4` | Players per room |

The staging server must be started with `TEST_AUTH_BYPASS=true` and
`TEST_JWT_SECRET=<same secret>` so it accepts the HS256 test tokens instead
of Clerk RS256 tokens.

---

## Running the Load Test

### Headless (CI / pre-release validation)

```bash
export TARGET_HOST=https://staging.example.com
export TEST_JWT_SECRET=<shared-secret>

locust \
  -f load-tests/websocket_load.py \
  --host "$TARGET_HOST" \
  --users 500 \
  --spawn-rate 10 \
  --run-time 7m \
  --headless \
  --html load-tests/results/report.html \
  --csv load-tests/results/metrics
```

### Interactive (web UI)

```bash
locust \
  -f load-tests/websocket_load.py \
  --host https://staging.example.com
# Open http://localhost:8089
```

---

## Understanding the Output

After the test completes, Locust prints a summary table and the custom SLO
report is printed to stdout:

```
============================================================
  WEBSOCKET LATENCY SLO REPORT
============================================================
  roll_result            n=1234   mean=  42.1ms  p50=  38.0ms  p95=  95.3ms  p99= 130.4ms  ✓ PASS
  state_update           n=1234   mean=  45.7ms  p50=  41.2ms  p95= 102.1ms  p99= 140.8ms  ✓ PASS
  pong                   n= 617   mean=   5.2ms  p50=   4.8ms  p95=   9.1ms  p99=  12.0ms  ✓ PASS
============================================================
  ALL SLOs PASSED  (SLO: p95 < 150ms)
============================================================
```

CSV reports are written to `load-tests/results/metrics_*.csv`.
HTML report is written to `load-tests/results/report.html`.

---

## Maximum Concurrent Connections Test (AC-7)

To identify the maximum concurrent connections before p95 latency exceeds 150ms,
run the load test with progressively higher `--users` values and observe when
the p95 latency in the SLO report first exceeds the 150ms threshold:

```bash
for USERS in 100 200 300 400 500 600 700; do
  echo "=== Testing with $USERS users ==="
  locust \
    -f load-tests/websocket_load.py \
    --host "$TARGET_HOST" \
    --users "$USERS" \
    --spawn-rate 20 \
    --run-time 3m \
    --headless \
    --html "load-tests/results/report_${USERS}users.html" \
    --csv "load-tests/results/metrics_${USERS}users" \
    2>&1 | grep -E "(SLO|p95|PASS|FAIL)"
done
```

---

## Running Unit Tests

```bash
cd /path/to/repo
pip install -r load-tests/requirements.txt
pytest load-tests/tests/ -v
```

---

## Test Configuration Reference

The exact test configuration is captured in `ScenarioConfig` in
`load-tests/websocket_load.py` under `DEFAULT_SCENARIO`:

```python
ScenarioConfig(
    users=500,
    rooms=125,
    players_per_room=4,
    ramp_up_seconds=120,
    sustain_seconds=300,
    ramp_down_seconds=60,
    p95_slo_ms=150.0,
)
```

This ensures results are reproducible — run the same file, same config,
same staging environment, and you get comparable numbers.

---

## Constraints

- **Staging only** — the `TARGET_HOST` must point to staging. The CI workflow
  enforces this with a required environment (`staging`) that has its own
  secrets.
- **JWT tokens** — test tokens are HS256-signed with `TEST_JWT_SECRET`. The
  staging server must be configured to accept them via `TEST_AUTH_BYPASS`.
- **AWS Free Tier** — a 7-minute run with 500 connections generates moderate
  traffic. Monitor CloudWatch for data transfer costs after each run.
