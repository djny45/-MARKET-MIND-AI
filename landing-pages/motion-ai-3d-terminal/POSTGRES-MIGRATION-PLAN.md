# PostgreSQL migration implementation plan (all remaining stores)

Status: **plan only** — no implementation, no provisioning, no production change.
Evidence: `backend/app/*.py` at PR #115 head `cca0a193`; PR #117 (`f3b4897`)
provides the reusable foundation (`postgres.py`, versioned advisory-locked
migrations, `postgres_market_store.py`); PR #118 (`fee2f37`) provides the
SQLite/PostgreSQL parity-test pattern.

## Current coverage

- PostgreSQL: market bars, ingestion audit, schema_migrations (PR #117/#118).
- Everything else: SQLite or in-memory. 20 modules reference `sqlite3`;
  `audit_events.py` is an in-memory bounded deque.

## Migration waves (dependencies first, each wave independently reversible)

### Wave 0 — shared foundation (already in PR #117)
Reuse `database_url()`, bounded readiness probe, advisory-lock migration
runner, and the `schema_migrations` version table. Add per-store version rows;
never auto-migrate at runtime — migrations remain opt-in from CI/operator.

### Wave 1 — identity and security (highest risk)
Stores: `user_auth.py`, `auth_session_store.py`, `authorization.py`,
`n8n_reviewer_security.py`, `audit_events.py`, `audit_integrity.py`.
- Convert `auth_sessions` table and session TTL/rotation semantics to
  `TIMESTAMPTZ`; preserve token hashing exactly.
- Move `audit_events` from the in-memory deque to an append-only table with
  the same redaction pipeline (`redact()`, bearer/entropy filters) and bounded
  retention; keep an in-memory read cache only if needed for latency.
- Gate: existing auth/session tests + new parity tests for TTL expiry,
  rotation, redaction and concurrent writes.

### Wave 2 — durable queue, leases and recovery
Stores: `distributed_queue.py`, `research_checkpoint_store.py`,
`analytical_agent_tasks.py`.
- Move job rows, lease deadlines (`lease_expires_at`), idempotency keys,
  at-least-once delivery markers, retry counters and supervisor heartbeats to
  PostgreSQL rows with `FOR UPDATE SKIP LOCKED` claiming.
- Preserve `MAX_CLAIM_LEASE_SECONDS` validation and two-process lease-race
  semantics; keep checkpoints and quality evaluations in the same transaction
  boundary where atomicity is required.
- Gate: existing two-process lease tests, concurrent claim/idempotency tests,
  recovery-after-crash drill.

### Wave 3 — agent state, memory, workflow lifecycle
Stores: `worker_memory.py`, `learning_feedback.py`, `n8n_workflow_lifecycle.py`,
`n8n_workflow_authoring.py`, `research_promotion_review.py`,
`research_benchmark_store.py`, `agent_network.py`.
- Port `worker_memory`, workflow drafts/reviews, benchmark and promotion
  records with unchanged column names/types; use JSONB only where SQLite
  stored JSON text, keeping read parity.
- Gate: parity tests for reads/writes/sorts and permission checks.

### Wave 4 — market-adjacent and reporting stores
Stores: `market_store.py` (legacy), `market_events.py`, `instrument_master.py`,
`daily_intelligence.py`, `watchlist.py`, `paper_trading/store.py`,
`workspace.py`, `zulip_notifier.py`, `sqlite_tuning.py`.
- Retire `sqlite_tuning.py` pragmas for PostgreSQL (connection pool settings
  instead); keep paper-trading virtual-only (`broker_execution=False`).
- Gate: market-store parity (PR #118) extended to watchlists/instruments and
  paper portfolios.

## Per-wave acceptance criteria

1. Versioned migration SQL in `backend/app/postgres_migrations/` with
   advisory lock; no runtime auto-migration.
2. Adapter module per store with the **same public contract** as the SQLite
   version; runtime selection remains explicit and opt-in.
3. Parity tests against a disposable PostgreSQL 16 service (CI pattern from
   PR #117/#118) covering happy path, malformed input, permissions,
   concurrency, cleanup and cancellation.
4. No DSN, password or exception text in logs/responses; redaction preserved.
5. Rollback documented per wave (schema down-migration + config revert).

## Implementation backlog — per-store contracts and gates

This is the authoritative task list derived from `POSTGRES-MIGRATION-GAP.md`.
Each row is one independently reversible migration PR. `DATABASE_URL` stays
unset until every row is merged and its gates pass. "Adapter contract" means
the PostgreSQL module exposes the same public functions, argument order and
return shape as the current SQLite implementation; callers switch by explicit
opt-in, never by auto-detection.

| # | Store / module | Wave | Migration and adapter contract | Parity, concurrency and security acceptance tests |
| --- | --- | --- | --- | --- |
| B0 | `postgres.py`, `schema_migrations` | 0 | Reuse PR #117 foundation: `database_url()` (never logs DSN), bounded readiness probe, advisory-lock versioned migration runner, opt-in from CI/operator only. Per-store version rows. | Empty-DB migration, idempotent re-run, version conflict rejection, no DSN/exception text in logs or API responses. |
| B1 | `user_auth.py`, `auth_session_store.py`, `authorization.py`, `n8n_reviewer_security.py` | 1 | Port user and session tables with `TIMESTAMPTZ` deadlines; preserve token hashing and bearer-only operator policy exactly. Adapter keeps create/rotate/revoke/verify signatures. | TTL expiry, rotation, bearer-only denial, malformed token rejection, concurrent session writes, timing behaviour preserved. |
| B2 | `audit_events.py`, `audit_integrity.py` | 1 | Replace bounded in-memory deque with append-only table; keep `redact()`, bearer/entropy filters and retention; read cache only if latency requires. | Redaction parity, append-only enforcement, retention/capacity, concurrent append integrity, no secret leakage. |
| B3 | `distributed_queue.py`, `research_checkpoint_store.py`, `analytical_agent_tasks.py` | 2 | Job rows, `lease_expires_at`, idempotency keys, delivery markers, retry counters and heartbeats as PostgreSQL rows; claim via `FOR UPDATE SKIP LOCKED`; checkpoints in same transaction where atomicity is required. | Two-process lease race, idempotent claim, recovery after simulated crash, `MAX_CLAIM_LEASE_SECONDS` validation, cancellation/cleanup. |
| B4 | `worker_memory.py`, `learning_feedback.py`, `research_promotion_review.py`, `research_benchmark_store.py`, `agent_network.py` | 3 | Same columns/types; JSONB only where SQLite stored JSON text, preserving read order/shape. Adapter keeps query/sort/update signatures. | Read/write/sort parity, permission checks, malformed-input rejection, concurrent update behaviour. |
| B5 | `n8n_workflow_lifecycle.py`, `n8n_workflow_authoring.py` | 3 | Draft/review/activation records with unchanged status semantics; no workflow activation or execution added by the migration. | Lifecycle transition parity, reviewer permission checks, idempotent duplicate events, no external writes in tests. |
| B6 | `market_store.py` (legacy), `market_events.py`, `instrument_master.py`, `daily_intelligence.py`, `watchlist.py` | 4 | Extend the PR #117/#118 market adapter to legacy store and watchlists/instruments; keep provenance labels (`status`, `source`, `retrieved_at`) and `SYNTHETIC` marking. | Extended market-store parity, provenance label parity, malformed-input rejection, read ordering. |
| B7 | `paper_trading/store.py`, `sqlite_tuning.py` | 4 | Virtual-only paper portfolios; replace SQLite pragmas with connection-pool settings. `broker_execution=False` remains permanent. | Portfolio parity, virtual-only assertion, no order/wallet/exec path introduced, resource-limit behaviour. |
| B8 | `workspace.py`, `zulip_notifier.py` | 4 | Workspace state and notifier delivery records; outbound notification behaviour unchanged and authorize-only. | Permission checks, duplicate-event suppression, injected-failure/retry path, no credentials in logs. |

Dependency order: B0 → B1/B2 → B3 → B4/B5 → B6/B7/B8. Wave 1 must precede
Wave 2 because queue authorization depends on identity/session semantics; Wave
2 must precede Waves 3–4 because workflow and reporting stores reference task
and lease records.

Definition of done for each row: versioned migration SQL, adapter with the same
public contract, parity/concurrency/security tests on disposable PostgreSQL 16,
redaction preserved, down-migration and config-revert documented, and no runtime
auto-migration. A market-data-only adapter (B6 foundation from PR #117/#118)
satisfies **only** its own row; it must never be reported as full application
persistence.

## Scope-out option (release decision)

The terminal demo release can proceed with `DATABASE_URL` **unset** and market
data only (PR #117/#118 explicitly scoped out). In that case this entire plan
is future work and must be recorded as such in release notes; no partial
migration may be described as complete.

## Research-only boundary (unchanged)

`broker_execution=False` permanently; no wallet signing, no order routing, no
real-money execution. All parity work is for research/paper state only.
