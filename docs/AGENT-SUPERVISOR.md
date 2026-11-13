# Bounded analytical-agent supervisor

## Purpose

The supervisor endpoint runs one bounded cycle over persisted research tasks:

1. Requeue tasks left in `running` beyond a configured stale-task grace period.
2. Select up to a configured number of queued tasks.
3. Execute them with bounded concurrency on the current API process.
4. Return recovery and dispatch summaries.
5. Acquire a singleton SQLite lease so overlapping supervisor cycles against the same database are rejected.

This reduces operator steps while preserving the task lifecycle audit trail.

## API

`POST /api/analytical-agent-supervisor/run`

Example request body:

```json
{
  "limit": 50,
  "max_concurrency": 4,
  "stale_after_seconds": 900
}
```

Bounds:
- `limit`: 1–550 tasks per cycle.
- `max_concurrency`: 1–16 concurrent tasks.
- `stale_after_seconds`: 60–86,400 seconds.

The route is protected by the workspace authentication middleware. Mutating requests require the authenticated session, trusted Origin, and CSRF header. Do not expose it publicly or store browser session cookies in an unattended scheduler.

## Result interpretation

The response includes:
- `recovery`: stale tasks requeued and tasks stopped after the execution-attempt limit.
- `dispatch`: number of queued tasks selected and successfully claimed/executed, plus bounded dispatch errors.
- `cycle_mode`: `single_process_single_cycle`.

An idle dispatch is a successful cycle with no queued tasks. A task can still finish in `failed` status; inspect its task detail and audit events to diagnose it.

## Operational boundaries

- This endpoint performs one cycle only. It does not start a daemon or schedule future cycles.
- Each cycle acquires a singleton SQLite lease with a one-hour expiry, renews it every two minutes during the cycle, and releases its exact lease token on completion. A crash leaves the lease until expiry; an operator should account for this before retrying.
- The lease serializes cycles only when processes share the same SQLite database file. It is not a cross-host distributed lock and does not coordinate separate database copies.
- The SQLite task records are durable, but execution and concurrency are process-local. Active task claims renew their heartbeat every 60 seconds with a claim-token fence, so healthy long-running work is not mistaken for stale work. Completion and optional evidence/memory sidecars are also claim-token fenced.
- Do not run multiple public API workers as though this were a distributed queue. The claim operation prevents duplicate claims in SQLite, but there is no distributed worker lease, broker, or cross-host supervisor.
- Startup recovery and the cycle's recovery operation only requeue stale work; they do not imply that the task is safe to execute against live market feeds.
- The shared intelligence provider may be unavailable. The task records this explicitly; no provider key is required for the deterministic task lifecycle tests.
- All tasks are research-only. No brokerage credentials, trade recommendations, order routing, or execution are part of the supervisor.

Before unattended scheduling is added, implement a dedicated service identity or machine-to-machine authentication, a single-owner scheduler, operational monitoring, and host-specific recovery tests.
