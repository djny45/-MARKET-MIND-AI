# Architecture Decision Records (research-only platform)

Status: verified against the current audit branch based on
`origin/main` commit `308e1ff066b700cfad9f8c1a408e2563ef2e0582` (2026-11-23).

## ADR-001 — Single-host SQLite task queue remains the supported runtime

**Decision.** Keep SQLite + one `agent-supervisor` as the supported execution
runtime. `backend/app/distributed_queue.py` is a design contract only: no
external broker, no multi-host runtime, no claim of multi-host support.

**Evidence.** `docker-compose.yml` defines one `backend` and one
`agent-supervisor` sharing volume `market_mind_data`; `QueueCapabilities()`
reports `multi_host_supported=False`; `backend/requirements.txt` contains no
broker dependency.

**Consequences.** No multi-host test is claimed. PR #38's lease implementation
was not ported because it targets an obsolete supervisor architecture. Future
supervisor leadership work is gated by
[ADR-0001](ADR-0001-DURABLE-QUEUE-AND-SUPERVISOR-LEASE.md), which is design-only
and explicitly retains single-host SQLite until contract and two-process tests
pass.

## ADR-002 — Market data is provenance-tagged and licenses are gated

**Decision.** Market-data batches carry `status`, `source`, `retrieved_at` and
warnings (`backend/app/market_data.py`). `data_licensing_gate.py` blocks
unauthorized sources; `provider_health.py` reports freshness without external
calls. Synthetic fixtures are labelled `SYNTHETIC`.

**Evidence.** `/api/market-data/sample` returns a labelled synthetic batch;
Yahoo/Stooq adapters return `HISTORICAL` with "not real-time/execution-grade"
warnings; `/api/providers/status` reports `no_live_provider_configured`.

**Gap recorded.** `POST /api/market-data/store` accepts caller-supplied
`status`/`source` without attestation; server-derived labelling is required
before this control can be called complete. No live provider is configured, so
no claim about current market prices is permitted.

## ADR-003 — Imported execution code stays inert

**Decision.** AutoHedge signing/order modules, FinceptTerminal and Freqtrade
live-bot code remain reference-only. They are not imported, built or executed.
No wallet private keys, transaction signing, live order routing or
market-making execution exists.

**Evidence.** Diagnostics report `broker_execution: false`; skill integrity
rejects `broker_execution`; the read-only MCP server forbids brokerage actions.

## ADR-004 — Frontend verification uses the existing esbuild/React toolchain

**Decision.** Keep React 18 + TypeScript + custom esbuild build. Component
tests use Vitest + jsdom + Testing Library, not a build-system migration.

**Evidence.** `npm run build` runs `scripts/build.mjs`; 10 node:test and 117
Vitest tests pass. `vite` and `vitest` are dev-only, not runtime dependencies.

## ADR-005 — Preserve divergent local work without rewriting history

**Decision.** Local `main` had 56 commits absent from origin and 8,789 tracked
files (including generated artifacts). It was preserved at
`recovery/local-main-56-commits` with source patches under `/tmp/opencode/`;
no force-push, reset, rebase, merge or discard was performed. Authoritative
development continues from `origin/main`.

## ADR-006 — Motion AI terminal PostgreSQL bootstrap remains held in demo mode

**Status:** Accepted for the current terminal release; production database enablement is not authorized by this record.

**Decision.** Keep `DATABASE_URL` unset for the Motion AI 3D terminal. The terminal remains in its explicitly labelled read-only demo mode until a separately reviewed PostgreSQL migration covers every required application store, the migration and adapters have parity/concurrency/security tests, and the maintainer explicitly approves a named deployment and each operational step. A market-data-only PostgreSQL adapter is not a complete application migration.

**Context and evidence.** The terminal's `/api/health` returns an honest `503` with `database=unconfigured` when no DSN is configured. The local demo verification reports `demoMode: true`; `verify-terminal.mjs` passed 34/34 and `verify-unreachable-db.mjs` passed 21/21, with exit code 0 and no production configuration changes. The current `POSTGRES-MIGRATION-GAP.md` identifies remaining SQLite/in-memory stores for workflow lifecycle, agent tasks/leases, auth/sessions, audit events, worker memory, durable recovery, and legacy market data. `POSTGRES-MIGRATION-PLAN.md` defines phased migration work and parity gates. These tests establish demo-mode behavior, not database-backed production readiness.

**Consequences.** Do not set `DATABASE_URL`, provision or migrate a production database, remove demo disclosures, enable public ingress, or promote a deployment as part of this release. `MARKET_MIND_API_URL` is a separate read-only backend integration setting and is not a substitute for `DATABASE_URL`. Do not describe a market-data adapter alone as full application persistence.

**Reversal criteria.** A future ADR or explicit maintainer amendment must identify the target Vercel project/environment and reviewed deployment SHA; document database ownership, backup/restore and rollback; demonstrate migrations/adapters and parity tests for every in-scope store; pass security review; and obtain formal independent approval. TLS, network segmentation and independent penetration testing remain separate prerequisites for public ingress.

**Rollback.** Keep the current demo configuration and revert any proposed environment-variable or deployment change. No production database change is authorized by ADR-006.
