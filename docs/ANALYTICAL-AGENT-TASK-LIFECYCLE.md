# Analytical-agent task lifecycle

This document describes the implemented task lifecycle and its current execution boundaries.

## Lifecycle

- **Queue:** `POST /api/research/route-and-queue` routes a brief to selected worker profiles and queues tasks for process-local background execution.
- **Explicit dispatch:** `POST /api/analytical-agent-supervisor/dispatch` dispatches a bounded queued-task snapshot. It is process-local, not a durable distributed queue.
- **Inspect:** `GET /api/analytical-agent-tasks/{task_id}` returns task state and stored result.
- **Audit:** `GET /api/analytical-agent-tasks/{task_id}/audit` returns bounded, cursor-paginated lifecycle events.
- **Cancel:** `POST /api/analytical-agent-tasks/{task_id}/cancel` changes a task from `queued` to `cancelled`. It cannot interrupt a task already claimed as `running`, nor alter completed/failed/cancelled tasks.
- **Retry:** `POST /api/analytical-agent-tasks/{task_id}/retry` accepts only failed tasks and creates a *new* queued task with the original input. One retry per original task is allowed. It does not automatically dispatch or rerun in place; the new task must be explicitly dispatched.
- **Recover:** on backend startup, stale `running` tasks are requeued automatically (best-effort) after the recovery grace period. `MARKET_MIND_STARTUP_RECOVERY=false` disables this behavior. `POST /api/analytical-agent-tasks/recover` remains available for manual recovery. Recovery does **not** dispatch tasks; dispatch remains explicit. A task is allowed at most three execution claims; a stale task already at that limit is moved to `failed` with a sanitized `ExecutionAttemptLimit` result instead of being requeued again.

## State and safety properties

- A task is claimed with a conditional `queued` → `running` update, preventing duplicate dispatch from claiming the same queued task.
- While execution is active, a background lease heartbeat refreshes `updated_at` only when the task is still `running` under the same execution token. This prevents ordinary long-running tasks from being mistaken for stale work; a stopped process stops refreshing and remains eligible for grace-period recovery.
- Cancellation uses a conditional `queued` → `cancelled` update, so it cannot cancel a task after it has been claimed.
- Task transitions are recorded in SQLite audit events.
- Task input is bounded and JSON-validated before persistence.
- The worker context is isolated by worker ID and context hash, while inference uses one shared intelligence provider.
- Research uses supplied data only; it does not fetch live market data or execute trades.
- Optional quality evaluation is a deterministic **structural source-reference/traceability check**. It does not establish factual correctness, predictive model quality, or trading profitability.

## Not implemented by this lifecycle

- Distributed/cloud queue or broker-backed scheduling. SQLite task claims and token-fenced heartbeats coordinate shared-database task ownership, but this is not a substitute for a production distributed queue or high-availability scheduler.
- Scheduled research or cloud workspaces. Stale recovery is bounded to three execution claims per task; manual retry creates a separate fresh task and is capped at one retry per failed original.
- Live market-data execution as part of the task runner.
- Broker or exchange order execution.
- Independent model instances or continuous autonomous training for 550 workers.

## Relevant tests

The backend task tests cover queue persistence, dispatch and single-claim behavior, task audit history, stale recovery, task metrics, optional traceability evaluation, and queued cancellation/terminal-state protection. The repository's GitHub Actions quality workflow is the authoritative CI status.
