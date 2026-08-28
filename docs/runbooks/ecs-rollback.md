# Runbook: ECS Deployment Rollback

**Service:** `ashta-chamma-api` ECS Fargate Service  
**Severity:** P1 (if production is degraded) / P2 (if staging only)  
**Last reviewed:** 2025-01-27

---

## Symptoms

- Health check endpoint `GET /api/health` returns non-200 or times out.
- ECS service shows tasks in `STOPPED` or `PENDING` state with restart loops.
- CloudWatch alarm `ecs-task-error-rate` fires.
- GitHub Actions deployment step failed but partial rollout occurred.
- Increased 5xx error rate observed in ALB access logs.

---

## Diagnosis Steps

1. **Check ECS service events** for deployment failures:

   ```bash
   aws ecs describe-services \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api \
     --query 'services[0].events[:10]'
   ```

2. **Identify the current and previous task definitions:**

   ```bash
   aws ecs describe-services \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api \
     --query 'services[0].{current: taskDefinition, desired: deployments[0].taskDefinition}'
   ```

3. **Check stopped task exit codes and reason:**

   ```bash
   aws ecs list-tasks \
     --cluster ashta-chamma-cluster \
     --family ashta-chamma-api \
     --desired-status STOPPED \
     --query 'taskArns[:5]'
   # Then describe each stopped task:
   aws ecs describe-tasks \
     --cluster ashta-chamma-cluster \
     --tasks <task-arn> \
     --query 'tasks[0].containers[0].{exitCode: exitCode, reason: reason}'
   ```

4. **Tail application logs** for error messages:

   ```bash
   aws logs tail /ecs/ashta-chamma-api --follow --since 10m
   ```

5. **Verify image pull succeeded:**  
   Check ECS task events for `CannotPullContainerError`. If ECR image is missing,
   the problem is in the CI/CD pipeline, not the application.

6. **Check deployment circuit breaker status:**

   ```bash
   aws ecs describe-services \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api \
     --query 'services[0].deployments[0].rolloutState'
   ```

   A value of `FAILED` means the circuit breaker already triggered an automatic
   rollback. Proceed to verify the rollback completed correctly.

---

## Resolution Steps

### Option A — Automatic circuit breaker rollback (preferred)

ECS deployment circuit breaker is enabled. If the new task definition fails to
reach `RUNNING` state within the configured threshold (2 failures), ECS
automatically rolls back to the previous task definition.

1. Confirm automatic rollback triggered:

   ```bash
   aws ecs describe-services \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api \
     --query 'services[0].deployments[*].{id: id, status: status, rolloutState: rolloutState}'
   ```

2. Wait for the rollback to complete (tasks reach steady state):

   ```bash
   aws ecs wait services-stable \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api
   ```

3. Verify health check passes:

   ```bash
   curl -sf https://api.ashta-chamma.example.com/api/health | jq .
   ```

### Option B — Manual rollback to previous task definition

Use when the circuit breaker did not trigger automatically or when you need
to roll back to a specific revision.

1. Find the previous stable task definition revision:

   ```bash
   aws ecs list-task-definitions \
     --family-prefix ashta-chamma-api \
     --sort DESC \
     --query 'taskDefinitionArns[:5]'
   ```

2. Update the ECS service to the previous revision:

   ```bash
   aws ecs update-service \
     --cluster ashta-chamma-cluster \
     --service ashta-chamma-api \
     --task-definition ashta-chamma-api:<PREVIOUS_REVISION> \
     --force-new-deployment
   ```

3. Wait for stabilization and verify:

   ```bash
   aws ecs wait services-stable \
     --cluster ashta-chamma-cluster \
     --services ashta-chamma-api
   curl -sf https://api.ashta-chamma.example.com/api/health | jq .
   ```

### Option C — AWS Console rollback

1. Open **ECS** → **Clusters** → `ashta-chamma-cluster` → **Services** →
   `ashta-chamma-api`.
2. Click **Update service** → **Force new deployment**.
3. Under **Task definition**, select the previous revision from the dropdown.
4. Click **Update** and monitor the **Deployments** tab.

---

## Post-Rollback Verification

- [ ] `GET /api/health` returns `{"status": "ok"}` with HTTP 200.
- [ ] ECS service shows desired count of running tasks (minimum 2 in production).
- [ ] CloudWatch alarms return to `OK` state.
- [ ] Spot-check a game WebSocket connection: verify rooms can be created and joined.
- [ ] Check ALB 5xx error rate drops to baseline in CloudWatch.

---

## Escalation Path

1. **On-call engineer** — initial triage (this runbook).
2. **Backend tech lead** — if root cause is application code; review commit diff.
3. **Infrastructure engineer** — if root cause is ECS, ECR, or CDK infrastructure.
4. **AWS Support** — open P1 case if ECS control plane is unresponsive.

**Slack channel:** `#ashta-chamma-incidents`  
**PagerDuty rotation:** `ashta-chamma-oncall`
