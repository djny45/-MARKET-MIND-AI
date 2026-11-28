# PostgreSQL migration gap assessment (2026-11-28)

Scope: MARKET-MIND-AI backend persistence. Evidence: `backend/app/*.py` on
`feature/motion-ai-3d-terminal` at `785f7e33`, plus PR #117 (`f3b4897`) and
PR #118 (`fee2f37`) diffs. No production database was provisioned or changed.

## Covered by PR #117 / #118 (market data only)

- `backend/app/postgres.py` — opt-in DSN read + bounded 3 s `SELECT 1` probe;
  never logs the DSN or exception text.
- `backend/app/postgres_market_migrations.py` — versioned, advisory-lock
  serialized migration creating `market_bars`,
  `market_ingestion_audit_events`, `schema_migrations`.
- `backend/app/postgres_market_store.py` — additive normalized market-bar
  adapter; does **not** switch the runtime store.
- PR #118 adds SQLite/PostgreSQL parity tests for batch writes, multi-source
  history, lineage, audit metadata and stored-data overview.
- CI: `postgres-market-store` (PostgreSQL 16 service) PASSES on both PR heads.

## Remaining gaps — still SQLite or in-memory (no PostgreSQL schema/adapter)

| Domain | Files | Current store | Evidence (`grep` counts) |
|---|---|---|---|
| Workflows / n8n lifecycle | `n8n_workflow_lifecycle.py`, `n8n_workflow_authoring.py` | SQLite + in-memory | 2 `sqlite3`, 4 `sqlite` refs |
| Agent tasks & leases | `analytical_agent_tasks.py`, `research_benchmark_store.py` | SQLite | 2 `sqlite3`, 18 `sqlite` refs |
| Authentication & sessions | `auth_session_store.py`, `user_auth.py`, `api_auth.py` | SQLite | 6 `sqlite3`, 10 `sqlite` refs |
| Audit events | `audit_events.py` | **in-memory bounded deque** | 0 `sqlite3`, 10 deque/dict refs |
| Worker memory | `worker_memory.py`, `learning_feedback.py` | SQLite | 2 `sqlite3`, 4 `sqlite` refs |
| Durable job recovery | `distributed_queue.py`, `research_checkpoint_store.py` | SQLite + in-memory | 2 `sqlite3`, 7 `sqlite` refs; leases tracked in memory |
| Market store (legacy) | `market_store.py` | SQLite | 5 `sqlite3`, 10 `sqlite` refs |

On this branch there are **no** `backend/app/postgres*.py` modules at all — the
PostgreSQL foundation exists only on PR #117/#118 branches.

## What the passing tests do and do not prove

- PR #117 tests prove: migration is opt-in/idempotent, advisory lock works,
  redacted failures, market-store adapter contract.
- PR #118 tests prove: the **market-store** public contract is equivalent
  between SQLite and PostgreSQL for the covered operations.
- They do **not** prove a complete application migration: no workflow, agent
  lease, session, audit-event, worker-memory or durable-recovery store has a
  PostgreSQL counterpart or parity test.

## PR #117/#118 dependency and merge order (no merge performed)

- `fee2f37` is a clean 3-commit descendant of `f3b4897`:
  `373ed279` (parity tests), `b3d85a01` (SQLite ordering fix),
  `fee2f37` (PostgreSQL ordering fix). It replaces
  `test_postgres_market_store_contract.py` with
  `test_postgres_market_store_parity.py`.
- Both PRs target `feature/motion-ai-3d-terminal`. Correct order:
  **merge #117 first, then #118**; alternatively squash the two-branch stack
  into one PR against `feature/motion-ai-3d-terminal`. Merging #118 first
  would duplicate/revert files.
- PR #117's earlier Trivy failure came from the archived import lockfile and
  is resolved by commit `e910f5fa` on PR #115; rebase/merge that fix before
  running final CI on the combined branch.

## Policy

`DATABASE_URL` stays unset in Vercel Production until all of the above stores
have migrations, adapters, parity tests and operator approval. No production
migration, provisioning or data change is authorized for this release.
