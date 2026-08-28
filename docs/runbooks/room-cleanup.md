# Runbook: Manual Room Cleanup

**Service:** Game room state in Redis + PostgreSQL  
**Severity:** P3 (operational hygiene) / P2 (stale rooms blocking resources)  
**Last reviewed:** 2025-01-27

---

## Symptoms

- Redis memory utilization is unexpectedly high due to accumulated stale room keys.
- CloudWatch alarm `redis-memory-high` fires (> 70% of `maxmemory`).
- RDS `rooms` table contains rooms in `in_progress` status with no active connections
  that are days old (orphaned rooms).
- Players report they cannot join rooms that appear active but have no live players.
- Operational query shows hundreds of rooms with `status = 'in_progress'` and
  `started_at` older than 24 hours.

---

## Diagnosis Steps

1. **Count stale rooms in Redis:**

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls KEYS 'room:*' | wc -l"
   ```

2. **Check Redis memory usage:**

   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ElastiCache \
     --metric-name FreeableMemory \
     --dimensions Name=ReplicationGroupId,Value=ashta-chamma-redis \
     --start-time $(date -d '1 hour ago' --utc +%Y-%m-%dT%H:%M:%SZ) \
     --end-time $(date --utc +%Y-%m-%dT%H:%M:%SZ) \
     --period 60 \
     --statistics Minimum
   ```

3. **Query PostgreSQL for orphaned rooms** (rooms marked `in_progress` for > 2 hours
   with no active players):

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "psql \$DATABASE_URL -c \"
     SELECT id, code, status, started_at,
            NOW() - started_at AS age
     FROM rooms
     WHERE status = 'in_progress'
       AND started_at < NOW() - INTERVAL '2 hours'
     ORDER BY started_at ASC
     LIMIT 50;\""
   ```

4. **Check active WebSocket connections per room** via Redis:

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls KEYS 'room:*:players'"
   ```

   For each suspicious room: `SCARD room:{id}:players` — a count of 0 confirms
   no active connections.

---

## Resolution Steps

### Step A — Clean up stale Redis room keys

Use when Redis memory is high due to rooms whose TTL has not expired or was
never set.

1. List room keys older than 2 hours (check key age via object encoding):

   ```bash
   # Get all room state keys
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls \
       --scan --pattern 'room:*:state'"
   ```

2. For each confirmed-orphaned room (no active players, > 2 hours old):

   ```bash
   # Delete all keys for a specific room
   ROOM_ID="<room-uuid>"
   redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls DEL \
     "room:${ROOM_ID}:state" \
     "room:${ROOM_ID}:players" \
     "room:${ROOM_ID}:chat"
   ```

   **Note:** Always confirm the room is orphaned before deleting. A running game
   will be instantly terminated.

3. Alternatively, set a TTL on stale keys to let Redis expire them naturally:

   ```bash
   ROOM_ID="<room-uuid>"
   redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls EXPIRE \
     "room:${ROOM_ID}:state" 300  # expires in 5 minutes
   ```

### Step B — Mark orphaned PostgreSQL rooms as abandoned

Update the database status for rooms that have been stuck in `in_progress` for
more than 2 hours with no active connections.

1. **Dry run** — preview what would be updated:

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "psql \$DATABASE_URL -c \"
     SELECT id, code, status, started_at
     FROM rooms
     WHERE status = 'in_progress'
       AND started_at < NOW() - INTERVAL '2 hours';\""
   ```

2. **Update rooms to `abandoned` status** (confirm the count in the dry run first):

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "psql \$DATABASE_URL -c \"
     UPDATE rooms
     SET status = 'abandoned',
         ended_at = NOW()
     WHERE status = 'in_progress'
       AND started_at < NOW() - INTERVAL '2 hours'
     RETURNING id, code;\""
   ```

3. Record the number of updated rooms in the incident log.

### Step C — Emergency full Redis flush (last resort)

**WARNING:** This deletes ALL game state including active games. Only use if
Redis memory is critically full and the cluster is at risk of evicting data
unpredictably.

1. Get confirmation from the **Backend tech lead** and **Infrastructure engineer**.
2. Notify players via a maintenance banner.
3. Flush all keys:

   ```bash
   redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls FLUSHALL
   ```

4. Force-recycle ECS tasks to reinitialize connection pools:

   ```bash
   aws ecs update-service \
     --cluster ashta-chamma-cluster \
     --service ashta-chamma-api \
     --force-new-deployment
   ```

### Step D — Prevent recurrence: ensure room TTLs are set

After cleanup, verify that the `RoomManager` service sets a Redis TTL on all
room keys at creation and on game end. Check `server/app/services/room_manager.py`.
The expected TTL is 24 hours (86400 seconds).

---

## Preventing Stale Rooms (Proactive)

The `RoomManager` includes a background cleanup task that marks rooms as
`abandoned` after 2 hours of inactivity. Verify it is running:

```bash
aws logs filter-log-events \
  --log-group-name /ecs/ashta-chamma-api \
  --filter-pattern "room cleanup" \
  --start-time $(date -d '2 hours ago' +%s000)
```

If no cleanup log entries appear in 2 hours, the background task may have
stopped. Force a service restart to reinitialize it.

---

## Post-Cleanup Verification

- [ ] Redis `KEYS 'room:*' | wc -l` returns a count proportional to active rooms.
- [ ] `FreeableMemory` CloudWatch metric has increased / returns to safe range.
- [ ] No rooms in PostgreSQL with `status = 'in_progress'` older than 2 hours.
- [ ] `GET /api/health` returns `{"status": "ok"}` with HTTP 200.
- [ ] New rooms can be created and joined successfully.

---

## Escalation Path

1. **On-call engineer** — initial triage and Steps A/B (this runbook).
2. **Backend tech lead** — Step C (emergency flush) requires tech lead approval.
3. **Infrastructure engineer** — if Redis memory is a recurring problem, evaluate
   upgrading the ElastiCache instance type or enabling Redis key eviction policies.

**Slack channel:** `#ashta-chamma-incidents`  
**PagerDuty rotation:** `ashta-chamma-oncall`
