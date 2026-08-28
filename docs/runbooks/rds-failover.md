# Runbook: RDS PostgreSQL Failover Procedure

**Service:** `ashta-chamma-db` RDS PostgreSQL 16 (Multi-AZ)  
**Severity:** P1  
**Last reviewed:** 2025-01-27

---

## Symptoms

- FastAPI returns 500 errors with `connection refused` or `timeout` in CloudWatch
  logs for database operations.
- CloudWatch metric `RDS/DatabaseConnections` drops to zero unexpectedly.
- CloudWatch alarm `rds-connection-failure` fires.
- Game rooms cannot be created; leaderboard queries fail.
- Application logs show `asyncpg.exceptions.ConnectionDoesNotExistError` or
  `sqlalchemy.exc.OperationalError`.

---

## Diagnosis Steps

1. **Check RDS instance status** in the console or CLI:

   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier ashta-chamma-db \
     --query 'DBInstances[0].{Status: DBInstanceStatus, AZ: AvailabilityZone, MultiAZ: MultiAZ}'
   ```

   Expected status: `available`. During failover: `failing-over`.

2. **Check RDS events** for recent failover or reboot activity:

   ```bash
   aws rds describe-events \
     --source-identifier ashta-chamma-db \
     --source-type db-instance \
     --duration 60 \
     --query 'Events[*].{Time: Date, Message: Message}'
   ```

3. **Verify application can reach RDS Proxy endpoint:**

   ```bash
   # From an ECS task (exec into running container):
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "pg_isready -h <RDS_PROXY_ENDPOINT> -p 5432 -U app"
   ```

4. **Check RDS Proxy health:**

   ```bash
   aws rds describe-db-proxies \
     --db-proxy-name ashta-chamma-proxy \
     --query 'DBProxies[0].Status'
   ```

5. **Examine application logs** for specific error patterns:

   ```bash
   aws logs filter-log-events \
     --log-group-name /ecs/ashta-chamma-api \
     --filter-pattern "OperationalError OR ConnectionDoesNotExistError" \
     --start-time $(date -d '30 minutes ago' +%s000)
   ```

---

## Resolution Steps

### Scenario A — Automatic Multi-AZ failover in progress

RDS Multi-AZ automatically promotes the standby instance. This takes 60–120 seconds.

1. Monitor RDS events until status returns to `available`:

   ```bash
   watch -n 10 "aws rds describe-db-instances \
     --db-instance-identifier ashta-chamma-db \
     --query 'DBInstances[0].DBInstanceStatus'"
   ```

2. RDS Proxy automatically reconnects to the new primary. No application code
   change is required because the application connects through RDS Proxy.

3. Verify connectivity via RDS Proxy after failover:

   ```bash
   aws ecs execute-command \
     --cluster ashta-chamma-cluster \
     --task <task-arn> \
     --container app \
     --interactive \
     --command "pg_isready -h <RDS_PROXY_ENDPOINT> -p 5432 -U app"
   ```

4. If ECS tasks are in a broken state due to failed connection pool initialization,
   force a new deployment to recycle tasks:

   ```bash
   aws ecs update-service \
     --cluster ashta-chamma-cluster \
     --service ashta-chamma-api \
     --force-new-deployment
   aws ecs wait services-stable \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api
   ```

### Scenario B — Manual failover trigger (planned maintenance)

Use during planned maintenance windows to test failover or migrate to a different
Availability Zone.

1. **Notify the team** in `#ashta-chamma-incidents` before proceeding.

2. Trigger failover:

   ```bash
   aws rds reboot-db-instance \
     --db-instance-identifier ashta-chamma-db \
     --force-failover
   ```

3. Monitor until status is `available` (typically 60–120 seconds).

4. Verify health check recovers:

   ```bash
   curl -sf https://api.ashta-chamma.example.com/api/health | jq .
   ```

### Scenario C — RDS instance unavailable (not a standard failover)

If the RDS instance is stuck in `incompatible-parameters` or similar non-failover
failure state:

1. Check parameter group and option group for recent changes:

   ```bash
   aws rds describe-db-instances \
     --db-instance-identifier ashta-chamma-db \
     --query 'DBInstances[0].{ParameterGroup: DBParameterGroups, Status: DBInstanceStatus}'
   ```

2. If a parameter group change caused the issue, restore to a known-good snapshot:

   ```bash
   aws rds describe-db-snapshots \
     --db-instance-identifier ashta-chamma-db \
     --query 'DBSnapshots[:5].{Id: DBSnapshotIdentifier, Time: SnapshotCreateTime, Status: Status}'
   ```

3. **Escalate to infrastructure engineer** before restoring from snapshot —
   this is a destructive operation with data loss risk.

---

## Post-Failover Verification

- [ ] `GET /api/health` returns `{"status": "ok"}` with HTTP 200.
- [ ] `POST /api/rooms` successfully creates a game room (tests DB write path).
- [ ] `GET /api/scores/leaderboard` returns data (tests DB read path).
- [ ] CloudWatch `RDS/DatabaseConnections` metric shows expected connection count.
- [ ] CloudWatch alarms return to `OK` state.
- [ ] Confirm no data loss by checking the latest game room `created_at` timestamps.

---

## Escalation Path

1. **On-call engineer** — initial triage (this runbook).
2. **Infrastructure engineer** — RDS configuration, parameter group, or snapshot restore.
3. **Database administrator** — schema corruption, replication lag, or data integrity issues.
4. **AWS Support** — open P1 case if RDS control plane is unresponsive or automatic
   failover does not complete within 5 minutes.

**Slack channel:** `#ashta-chamma-incidents`  
**PagerDuty rotation:** `ashta-chamma-oncall`
