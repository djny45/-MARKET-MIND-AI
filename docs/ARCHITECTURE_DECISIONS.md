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
