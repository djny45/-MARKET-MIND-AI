# ADR-0001: Durable queue provider and single-active supervisor

- Status: Partially implemented (ported from PR #39). The single-host SQLite
  supervisor lease (conditional acquisition, fenced heartbeats/release, expiry
  rejection and in-dispatch renewal) is implemented and tested. The broker/
  queue-provider interface and two-host contract tests remain proposed — see
  `docs/MULTI-HOST-ARCHITECTURE-ASSESSMENT.md`.
- Date: 2026-11-18
- Scope: research-task execution only; brokerage/order execution remains out of scope

## Context

The current deployment persists task records in SQLite and runs a dedicated polling supervisor. Task claims use conditional state transitions and execution-token fencing; stale-task recovery and concurrent recovery have regression coverage. This is a useful single-host baseline, but it is not a distributed queue.

The lifecycle has an important multi-supervisor hazard: two supervisor processes can both perform startup recovery and polling against the same database. Atomic task claims prevent duplicate execution of one queued row, but do not provide supervisor leadership, lease ownership, or a supported multi-host coordination contract. SQLite remains a single-host storage choice.

## Decision

Introduce a queue-provider boundary without changing the public task API or task state vocabulary. Keep the existing SQLite implementation as the default single-host provider. Do not advertise multi-host operation until a separately deployable provider with tested atomic claim/lease semantics exists.

The supervisor must acquire an exclusive, renewable lease before startup recovery or dispatch. A process that cannot acquire the lease must exit cleanly without recovering or dispatching tasks. The lease must be fenced by a monotonically increasing generation (or an equivalent unforgeable ownership token) so an expired former owner cannot renew, release, or mutate leadership state belonging to a newer owner.

## Required interfaces

- `QueueProvider.enqueue(task)`
- `QueueProvider.claim_batch(owner_id, lease_generation, limit)`
- `QueueProvider.heartbeat_claim(task_id, claim_token)`
- `QueueProvider.complete(task_id, claim_token, result)`
- `QueueProvider.fail(task_id, claim_token, error)`
- `QueueProvider.recover_expired_claims(now)`
- `SupervisorLease.acquire(owner_id, now, ttl)`
- `SupervisorLease.renew(owner_id, generation, now, ttl)`
- `SupervisorLease.release(owner_id, generation)`

The SQLite adapter must keep transactions short, use conditional updates, and preserve current audit events and execution-token fencing. Provider selection must be explicit and fail closed for unknown provider names; no silent fallback from a requested remote provider to SQLite.

## Lease semantics

1. Lease acquisition is atomic and succeeds only if no unexpired owner exists, or the same owner is renewing its own lease.
2. Every successful acquisition/renewal returns the current generation and expiry timestamp.
3. Renewal and release require both owner ID and generation; stale generations are rejected.
4. The supervisor renews at a bounded fraction of the TTL and stops dispatch immediately if renewal fails.
5. Startup recovery is permitted only after lease acquisition.
6. Shutdown releases only the lease generation held by that process. A failed release is observable and must not clear a newer owner's lease.
7. A crashed process is recoverable after lease expiry. Clock assumptions and maximum tolerated skew must be documented; SQLite single-host mode should use host wall-clock UTC and a conservative TTL.
8. Lease state and transitions are observable without exposing secrets or raw task payloads.

## Compatibility and migration

- Preserve existing task IDs, status values, task API routes, task audit schema, and current SQLite database.
- Add schema changes with idempotent migrations and explicit schema-version tests.
- Existing deployments default to the SQLite provider and remain single-host.
- Do not require Redis, RabbitMQ, cloud services, or paid APIs for the default path.
- If a Redis/PostgreSQL adapter is added later, document its operational prerequisites and run the same provider contract suite against it.
- Do not run two supervisors against the same SQLite database until lease acquisition and failure behavior are implemented and verified.

## Failure handling

- Lease unavailable: exit with a distinct non-zero startup result; do not run recovery.
- Lease renewal failure: stop accepting new work, allow in-flight task finalization only while claim fencing remains valid, then exit.
- Database unavailable: fail closed; do not report a healthy supervisor heartbeat.
- Task claim lost: discard stale completion and record a bounded diagnostic where safe.
- Provider configuration invalid: fail startup; never silently select another provider.
- Poison tasks: preserve bounded attempt limits and operator-visible failure classification; no unbounded automatic retries.

## Required tests before implementation can be marked complete

- Provider contract: bounded JSON provenance; concurrent claimers; expired-claim recovery exactly once; stale claim tokens rejected; completion/audit transactional consistency; migration preserves tasks and events.
- Supervisor lease: two-process race with exactly one winner; owner/generation-only renew and release; higher generation takeover after expiry; old owner cannot renew/release/dispatch; renewal failure stops polling; recovery never runs without a lease; SIGTERM release and crash expiry; malformed/stale records fail safely.
- Runtime and operations: process-kill/restart with persistent volume; two-supervisor integration test; bounded queue metrics; alert thresholds and runbook; load/contention test at the documented envelope.

## Acceptance gates

This ADR is a design decision, not an implementation claim. An **isolated
two-process SQLite race test** now exists
(`backend/tests/test_supervisor_two_process_race.py`): two real processes start
together, exactly one acquires leadership and dispatches the single queued
task, the loser performs no side effects, and the winner releases the lease.
This closes the single-host race check, not the full ADR: provider contract
tests, crash/restart against a persistent volume, and multi-host coordination
remain incomplete. Until then, the supported deployment remains a single-host
SQLite queue with one supervisor process.

## Explicit non-goals

- Brokerage, exchange order routing, or trade execution.
- 550 independent model instances or continuously running autonomous agents.
- Automatic model training or unreviewed skill/configuration promotion.
- A mandatory paid queue service.
- Claiming distributed guarantees from SQLite alone.
