# Runbook: Debugging WebSocket Disconnections

**Service:** WebSocket endpoint `wss://api.ashta-chamma.example.com/ws/rooms/{room_id}`  
**Severity:** P2 (isolated disconnects) / P1 (all connections dropping)  
**Last reviewed:** 2025-01-27

---

## Symptoms

- Players are unexpectedly disconnected mid-game and the client does not
  automatically reconnect.
- WebSocket connection is established but no messages are received (silent drop).
- Client console shows `WebSocket connection closed: code 1006` (abnormal closure).
- CloudWatch alarm `websocket-active-connections` drops sharply.
- Players report the game "freezes" or shows stale state.
- ALB access logs show 101 (Upgrade) followed by no further requests from the client.

---

## Diagnosis Steps

1. **Check ALB WebSocket idle timeout** — the most common cause of disconnections
   in long games:

   ```bash
   aws elbv2 describe-load-balancer-attributes \
     --load-balancer-arn <ALB_ARN> \
     --query 'Attributes[?Key==`idle_timeout.timeout_seconds`]'
   ```

   The value should be `3600` (1 hour). If it is `60` (default), connections
   will drop after 60 seconds of no messages — see Resolution Step A.

2. **Check ECS task health** — tasks crashing mid-request cause connection drops:

   ```bash
   aws ecs describe-services \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api \
     --query 'services[0].{runningCount: runningCount, pendingCount: pendingCount, desiredCount: desiredCount}'
   ```

3. **Examine WebSocket close codes** in ALB access logs:

   ```bash
   aws logs filter-log-events \
     --log-group-name /aws/alb/ashta-chamma \
     --filter-pattern '"101"' \
     --start-time $(date -d '30 minutes ago' +%s000) \
     --query 'events[*].message' | head -20
   ```

4. **Check application logs** for WebSocket disconnect events and errors:

   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/ashta-chamma-api \
     --filter-pattern "WebSocket OR disconnect OR websocket" \
     --start-time $(date -d '30 minutes ago' +%s000)
   ```

5. **Check Redis pub/sub health** — a Redis failure causes silent message drops
   without disconnecting the WebSocket:

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "redis-cli -h <REDIS_PRIMARY_ENDPOINT> -p 6379 --tls PUBSUB CHANNELS 'room:*'"
   ```

6. **Test a WebSocket connection manually** using `wscat` or a browser DevTools
   Network tab:

   ```bash
   wscat -c "wss://api.ashta-chamma.example.com/ws/rooms/<room_id>?token=<jwt>" \
     --timeout 60
   ```

   Send a `{"type":"ping"}` message and verify `{"type":"pong"}` is received.

7. **Check ECS task memory and CPU** — OOM kills cause abrupt connection drops:

   ```bash
   aws cloudwatch get-metric-statistics \
     --namespace AWS/ECS \
     --metric-name MemoryUtilization \
     --dimensions Name=ClusterName,Value=ashta-chamma-cluster \
                   Name=ServiceName,Value=ashta-chamma-api \
     --start-time $(date -d '1 hour ago' --utc +%Y-%m-%dT%H:%M:%SZ) \
     --end-time $(date --utc +%Y-%m-%dT%H:%M:%SZ) \
     --period 60 \
     --statistics Maximum
   ```

---

## Resolution Steps

### Step A — Fix ALB idle timeout (most common fix)

If the ALB idle timeout is less than the expected game duration:

```bash
aws elbv2 modify-load-balancer-attributes \
  --load-balancer-arn <ALB_ARN> \
  --attributes Key=idle_timeout.timeout_seconds,Value=3600
```

**Note:** This change takes effect immediately without a deployment. Verify by
holding an idle WebSocket connection open for 2+ minutes.

### Step B — Ensure client-side ping/pong keep-alive is active

The React client's `WebSocketManager` must send a `{"type":"ping"}` every 30
seconds. Check the client code in `client/src/services/WebSocketManager.ts`.

If the ping interval has been accidentally increased or disabled:
1. Restore the 30-second ping interval.
2. Deploy a new client build.

### Step C — ECS task OOM kill causing disconnections

If memory utilization is consistently above 85%:

1. Review recent application changes for memory leaks in connection handlers.
2. Temporarily increase task memory in the CDK stack:

   ```typescript
   // infra/lib/compute-stack.ts
   memoryLimitMiB: 2048,  // increase from 1024
   ```

   Then redeploy the CDK stack:

   ```bash
   cd infra
   npx cdk deploy ComputeStack
   ```

### Step D — Redis pub/sub broken, messages not delivered

If Redis is healthy but pub/sub messages are not reaching all clients (only the
client on the same Fargate task as the publisher receives updates):

1. Check aioredis subscriber state in application logs.
2. Force-recycle ECS tasks to re-establish Redis subscriptions:

   ```bash
   aws ecs update-service \
     --cluster ashta-chamma-cluster \
     --service ashta-chamma-api \
     --force-new-deployment
   ```

### Step E — ECS task crash-looping

If tasks are crashing and restarting, causing all WebSocket connections on that
task to drop:

- Follow the [ECS Rollback Runbook](./ecs-rollback.md) to deploy the previous
  stable task definition.

---

## Post-Resolution Verification

- [ ] Establish a WebSocket connection and verify it stays open for 5+ minutes
  with no activity (tests idle timeout fix).
- [ ] Send `{"type":"ping"}` and receive `{"type":"pong"}` within 1 second.
- [ ] Create a 2-player room on separate clients; verify both clients receive game
  state updates (tests pub/sub fan-out).
- [ ] CloudWatch `websocket-active-connections` metric returns to expected baseline.
- [ ] CloudWatch alarms return to `OK` state.

---

## Escalation Path

1. **On-call engineer** — initial triage (this runbook).
2. **Backend tech lead** — if root cause is application-level connection handling.
3. **Infrastructure engineer** — if root cause is ALB configuration, VPC, or
   ECS task resource limits.
4. **AWS Support** — open P2 case if ALB WebSocket routing shows unexpected behavior.

**Slack channel:** `#ashta-chamma-incidents`  
**PagerDuty rotation:** `ashta-chamma-oncall`
