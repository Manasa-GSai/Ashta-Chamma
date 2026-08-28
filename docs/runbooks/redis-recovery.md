# Runbook: Redis (ElastiCache) Connection Failure Recovery

**Service:** `ashta-chamma-redis` ElastiCache Redis cluster  
**Severity:** P1 (pub/sub fan-out down) / P2 (single-task games continue in-memory)  
**Last reviewed:** 2025-01-27

---

## Symptoms

- Application logs contain `aioredis.exceptions.ConnectionError` or
  `redis.exceptions.TimeoutError`.
- New WebSocket connections succeed but game state updates are not broadcast
  to all players (pub/sub fan-out broken across multiple ECS tasks).
- JWT JWKS cache is unavailable — every request triggers a Clerk JWKS fetch,
  causing latency spikes.
- CloudWatch alarm `redis-connection-failure` fires.
- Room state operations (`room:{id}:state` reads/writes) fail.

---

## Diagnosis Steps

1. **Check ElastiCache cluster status:**

   ```bash
   aws elasticache describe-replication-groups \
     --replication-group-id ashta-chamma-redis \
     --query 'ReplicationGroups[0].{Status: Status, NodeGroups: NodeGroups[0].NodeGroupMembers[*].{Role: CurrentRole, Status: CacheNodeStatus}}'
   ```

   Expected status: `available`. During failover: `snapshotting` or `modifying`.

2. **Check ElastiCache events** for recent failures or failovers:

   ```bash
   aws elasticache describe-events \
     --source-identifier ashta-chamma-redis \
     --source-type replication-group \
     --duration 60 \
     --query 'Events[*].{Time: Date, Message: Message}'
   ```

3. **Test connectivity from an ECS task:**

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls PING"
   ```

   Expected response: `PONG`. A timeout indicates a network or security group issue.

4. **Check VPC security groups** allow ECS tasks to reach Redis port 6379:

   ```bash
   aws ec2 describe-security-groups \
     --filters "Name=group-name,Values=ashta-chamma-redis-sg" \
     --query 'SecurityGroups[0].IpPermissions'
   ```

5. **Check application error logs** for connection pool exhaustion vs. network failure:

   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/ashta-chamma-api \
     --filter-pattern "aioredis OR redis.exceptions OR ConnectionError" \
     --start-time $(date -d '15 minutes ago' +%s000)
   ```

---

## Resolution Steps

### Scenario A — ElastiCache automatic failover (primary node failure)

ElastiCache Redis performs automatic primary promotion in 20–30 seconds when the
primary node fails.

1. Wait for the replication group status to return to `available`:

   ```bash
   watch -n 10 "aws elasticache describe-replication-groups \
     --replication-group-id ashta-chamma-redis \
     --query 'ReplicationGroups[0].Status'"
   ```

2. The application uses the **primary endpoint** (not individual node endpoints),
   so no configuration change is needed after failover.

3. Force-recycle ECS tasks to clear any stale aioredis connection pools:

   ```bash
   aws ecs update-service \
     --cluster ashta-chamma-cluster \
     --service ashta-chamma-api \
     --force-new-deployment
   aws ecs wait services-stable \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api
   ```

4. Verify Redis connectivity and pub/sub functionality:

   ```bash
   curl -sf https://api.ashta-chamma.example.com/api/health | jq .
   ```

### Scenario B — Redis connection pool exhaustion (not a failure)

If the logs show `Too many connections` or connection pool timeouts without a
cluster failure:

1. Check current active connections:

   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ElastiCache \
     --metric-name CurrConnections \
     --dimensions Name=ReplicationGroupId,Value=ashta-chamma-redis \
     --start-time $(date -d '30 minutes ago' --utc +%Y-%m-%dT%H:%M:%SZ) \
     --end-time $(date --utc +%Y-%m-%dT%H:%M:%SZ) \
     --period 60 \
     --statistics Maximum \
     --query 'Datapoints[*].{Time: Timestamp, Max: Maximum}' | sort -k2
   ```

2. If connections are unexpectedly high, check for connection leaks in recent
   deployments. Review the `aioredis` connection pool settings in
   `server/app/providers/redis_provider.py`.

3. Force-recycle ECS tasks to clear connection leaks:

   ```bash
   aws ecs update-service \
     --cluster ashta-chamma-cluster \
     --service ashta-chamma-api \
     --force-new-deployment
   ```

### Scenario C — Redis data recovery (games lost to Redis failure)

Redis state is intentionally ephemeral (no persistence). Games in progress during
a full Redis failure are lost. This is an accepted trade-off for the MVP.

1. Notify affected players via a maintenance banner (update CloudFront response).
2. Verify no stale keys remain after recovery:

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls KEYS 'room:*' | wc -l"
   ```

3. Stale room keys can be flushed manually if needed (confirm with tech lead first):

   ```bash
   # WARNING: This deletes ALL room state. Confirm with tech lead before running.
   redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls --scan --pattern 'room:*' | \
     xargs redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls DEL
   ```

---

## Post-Recovery Verification

- [ ] `GET /api/health` returns `{"status": "ok"}` with HTTP 200.
- [ ] Create a new game room and verify state is stored: `GET /api/rooms/{code}`.
- [ ] Connect two WebSocket clients to a room and verify state broadcasts to both.
- [ ] CloudWatch `CurrConnections` metric is within expected range (< 50 per task).
- [ ] CloudWatch alarms return to `OK` state.

---

## Escalation Path

1. **On-call engineer** — initial triage (this runbook).
2. **Infrastructure engineer** — ElastiCache configuration, VPC security groups,
   or cluster parameter group issues.
3. **AWS Support** — open P1 case if ElastiCache control plane is unresponsive
   or automatic failover does not complete within 5 minutes.

**Slack channel:** `#ashta-chamma-incidents`  
**PagerDuty rotation:** `ashta-chamma-oncall`
