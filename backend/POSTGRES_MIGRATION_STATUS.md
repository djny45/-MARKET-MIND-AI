# Vercel / PostgreSQL migration status

## Current deployment facts

- FastAPI is deployed as a Vercel Python function.
- `GET /api/health` is an HTTP liveness check only.
- `GET /api/postgres-readiness` probes the configured `DATABASE_URL` using psycopg and returns only redacted status.
- `GET /api/ready` is the application readiness gate. It must remain non-ready until every required persistent store is backed by durable storage and passes read/write/schema checks.
- The application is research-only. Broker execution and paper trading remain disabled.

## Persistence inventory verified in source

| Store | Current implementation | Required migration work |
|---|---|---|
| Market bars and ingestion audit | `backend/app/market_store.py` | PostgreSQL schema, transactional upsert, indexes, migration versioning |
| Workflows, runs, synthesis reviews | `backend/app/workspace.py` | PostgreSQL schema, JSON field compatibility, replace SQLite PRAGMA-based column checks |
| Agent tasks, retries, task events, supervisor heartbeat, quality evaluations | `backend/app/analytical_agent_tasks.py` | PostgreSQL schema, atomic task claiming, lease fencing, retry and event parity |
| User/session/auth state and security audit | `backend/app/user_auth.py`, `backend/app/audit_events.py`, and related modules | Identify every file-backed store; migrate transactionally and preserve session revocation/audit semantics |
| Worker memory and other research records | `backend/app/worker_memory.py` and related modules | Identify every file-backed store; migrate before enabling write endpoints |

This inventory is a starting point, not a claim that these are the only persistence modules. A full repository scan and per-store tests are required before declaring migration complete.

## Deployment safety rules

1. Do not use Vercel's writable filesystem as durable application storage.
2. Do not silently fall back to SQLite when `DATABASE_URL` is configured.
3. Do not treat a successful PostgreSQL connection probe as proof that application tables have migrated.
4. Keep `/api/ready` returning HTTP 503 until all required application persistence checks pass.
5. Do not enable long-running in-process supervisors in serverless functions. Task submission must persist a durable job; execution and recovery must be performed by a queue consumer or bounded scheduled worker with idempotent claims.
6. Preserve the current research-only boundary; no broker or order execution.

## Migration sequence

- [ ] Enumerate every SQLite/file-backed store and all SQL dialect assumptions.
- [ ] Define versioned PostgreSQL DDL and indexes for each store.
- [ ] Introduce a shared PostgreSQL connection/transaction layer with bounded connection lifetime/pooling suitable for serverless.
- [ ] Migrate one store at a time with SQLite/PostgreSQL parity tests.
- [ ] Add an explicit, resumable data export/import process with row counts, checksums, and rollback instructions.
- [ ] Replace SQLite-specific SQL (`?` placeholders, `PRAGMA table_info`, SQLite upsert syntax, autoincrement assumptions) and test concurrency semantics.
- [ ] Move task claiming, retry, recovery, and heartbeat to durable PostgreSQL/queue semantics.
- [ ] Run the complete backend test suite against PostgreSQL.
- [ ] Verify read/write readiness, authentication, CORS, frontend integration, and deployment logs.
- [ ] Promote only after all gates pass.

## Current blocker

PostgreSQL connectivity is configured and reachable in the Vercel preview, but the application readiness endpoint currently returns HTTP 503 because its existing SQLite storage check fails in the serverless runtime. The database probe and application persistence readiness are intentionally separate signals.
