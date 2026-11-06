# Analytical-agent task lifecycle

This document describes the implemented task lifecycle and its current execution boundaries.

## Lifecycle

- **Queue:** `POST /api/research/route-and-queue` routes a brief to selected worker profiles and queues tasks for process-local background execution.
- **Explicit dispatch:** `POST /api/analytical-agent-supervisor/dispatch` dispatches a bounded queued-task snapshot. It is process-local, not a durable distributed queue.
- **Inspect:** `GET /api/analytical-agent-tasks/{task_id}` returns task state and stored result.
- **Audit:** `GET /api/analytical-agent-tasks/{task_id}/audit` returns bounded, cursor-paginated lifecycle events.
- **Cancel:** `POST /api/analytical-agent-tasks/{task_id}/cancel` changes a task from `queued` to `cancelled`. It cannot interrupt a task already claimed as `running`, nor alter completed/failed/cancelled tasks.
- **Recover:** `POST /api/analytical-agent-tasks/recover` requeues stale `running` tasks after the recovery grace period. Recovery does **not** dispatch them; dispatch remains explicit.

## State and safety properties

- A task is claimed with a conditional `queued` → `running` update, preventing duplicate dispatch from claiming the same queued task.
- Cancellation uses a conditional `queued` → `cancelled` update, so it cannot cancel a task after it has been claimed.
- Task transitions are recorded in SQLite audit events.
- Task input is bounded and JSON-validated before persistence.
- The worker context is isolated by worker ID and context hash, while inference uses one shared intelligence provider.
- Research uses supplied data only; it does not fetch live market data or execute trades.
- Optional quality evaluation is a deterministic **structural source-reference/traceability check**. It does not establish factual correctness, predictive model quality, or trading profitability.

## Not implemented by this lifecycle

- Distributed/cloud queue or multi-process coordination.
- Automatic retry policy, scheduled research, or cloud workspaces.
- Live market-data execution as part of the task runner.
- Broker or exchange order execution.
- Independent model instances or continuous autonomous training for 550 workers.

## Relevant tests

The backend task tests cover queue persistence, dispatch and single-claim behavior, task audit history, stale recovery, task metrics, optional traceability evaluation, and queued cancellation/terminal-state protection. The repository's GitHub Actions quality workflow is the authoritative CI status.
