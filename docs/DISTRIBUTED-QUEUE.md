# Distributed multi-host research queue — design

Current platform: **single-host durable SQLite queue** with a
`agent-supervisor` service. This design defines the interface a distributed
multi-host queue must implement so the platform can scale beyond one host
without changing the research contract.

## Requirements for a distributed queue

- **Idempotency** — every job has an `idempotency_key`; duplicates are no-ops.
- **At-least-once** delivery with **lease-based claims** (conditional CAS);
  claimed jobs have `lease_expires_at`.
- **Retry policy** with `max_attempts` and exponential backoff; after the cap,
  jobs go to `deadletter` with a sanitized error and `replay_of` linkage.
- **Observability** — `stats()` must return queue depths by state and per-worker.
- **Capacity gating** — bounded payload, structured input validation at enqueue.
- **Header safety** — never persist non-deterministic runtime noise; every record
  has a stable ID, creation time, and user context.
- **Isolation** — multi-host stores must be transactional or lease-safe (e.g.
  Postgres with advisory locks, or Kafka with consumer groups + output
  deduplication).

## Interface (`MultiHostQueue`)

```python
from app.distributed_queue import Job, JobStatus

enqueue(queue_key, body, idempotency_key, parent_job_id=None) -> Job
claim(worker_id, lease_seconds) -> Job | None
complete(job, result=None) -> Job
fail(job, error) -> Job
cancel(job, reason) -> Job
stats() -> dict
```

Job states: `queued`, `running`, `completed`, `failed`, `cancelled`, `deadletter`.

## Current limitations (documented)

- The SQLite queue is single-host by design; multi-host ownership would break
  lease assumptions without an external store.
- No distributed broker (Kafka/Redis) is integrated.
- Workers are process-local; cloud workspaces and independent daemons are not
  planned.
- Retry policy is applied by the supervisor, not the broker, in the single-host
  path.

See `backend/app/distributed_queue.py` for the design dataclasses and
`backend/tests/test_distributed_queue.py` for the interface contract tests.
