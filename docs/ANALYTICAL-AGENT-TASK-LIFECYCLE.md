# Analytical-agent task lifecycle

This document describes the implemented task lifecycle and its current execution boundaries.

## Lifecycle

- **Queue:** `POST /api/research/route-and-queue` routes a brief to selected specialist profiles and commits each task to the shared SQLite database before returning.
- **Automatic dispatch:** in the private Compose deployment, the separate `agent-supervisor` service polls the shared SQLite volume, acquires a renewable singleton lease, and dispatches bounded batches. The API process does not schedule queued work in its own process.
- **Manual dispatch:** `POST /api/analytical-agent-supervisor/dispatch` remains an operator-triggered bounded dispatch endpoint that executes on the API process. It is not the production polling path and does not turn SQLite into a distributed queue.
- **Inspect:** `GET /api/analytical-agent-tasks/{task_id}` returns task state and stored result.
- **Audit:** `GET /api/analytical-agent-tasks/{task_id}/audit` returns bounded, cursor-paginated lifecycle events.
- **Cancel:** `POST /api/analytical-agent-tasks/{task_id}/cancel` changes a task from `queued` to `cancelled`. It cannot interrupt a task already claimed as `running`, nor alter completed/failed/cancelled tasks.
- **Retry:** `POST /api/analytical-agent-tasks/{task_id}/retry` accepts only failed tasks and creates a *new* queued task with the original input. One retry per original task is allowed. It does not automatically dispatch or rerun in place; the new task must be explicitly dispatched.
- **Recover:** the dedicated Compose supervisor performs stale-task recovery after acquiring its singleton lease. Compose explicitly sets `MARKET_MIND_STARTUP_RECOVERY=false` on the API service so an API restart cannot independently requeue a task still owned by the supervisor. Standalone single-process deployments may retain API startup recovery. `POST /api/analytical-agent-tasks/recover` remains available for controlled operator recovery; stop/quiesce the supervisor before invoking it. Recovery requeues but does not itself execute tasks. A task is allowed at most three execution claims; a stale task already at that limit is moved to `failed` with a sanitized `ExecutionAttemptLimit` result instead of being requeued again.

## State and safety properties

- A task is claimed with a conditional `queued` → `running` update, preventing duplicate dispatch from claiming the same queued task.
- Cancellation uses a conditional `queued` → `cancelled` update, so it cannot cancel a task after it has been claimed.
- Task transitions are recorded in SQLite audit events.
- Task input is bounded and JSON-validated before persistence.
- The worker context is isolated by worker ID and context hash, while inference uses one shared intelligence provider.
- Research uses supplied data only; it does not fetch live market data or execute trades.
- Optional quality evaluation is a deterministic **structural source-reference/traceability check**. It does not establish factual correctness, predictive model quality, or trading profitability.

## Not implemented by this lifecycle

- Distributed/cloud queue or multi-host coordination. The Compose topology uses one dedicated supervisor and a shared single-host SQLite database; do not run multiple independent supervisors or multiple API processes with startup recovery enabled against the same task database.
- Scheduled research or cloud workspaces. Stale recovery is bounded to three execution claims per task; manual retry creates a separate fresh task and is capped at one retry per failed original.
- Live market-data execution as part of the task runner.
- Broker or exchange order execution.
- Independent model instances or continuous autonomous training for 550 workers.

## Relevant tests

The backend task tests cover queue persistence, dispatch and single-claim behavior, task audit history, stale recovery, a subprocess restart simulation, concurrent recovery, supervisor lease fencing, graceful shutdown, startup-recovery failure, task metrics, optional traceability evaluation, and queued cancellation/terminal-state protection. The deployment checker also verifies that API startup recovery is disabled in the Compose topology. The repository's GitHub Actions quality workflow is the authoritative CI status.
