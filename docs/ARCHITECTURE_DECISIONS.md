# Architecture Decision Records (research-only platform)

Status: proposed/verified against `main` at commit `89c20dde0d9b0b2bebb0c309c970212fa321b459` (2026-11-22).

## ADR-001 — Single-host SQLite task queue remains the supported runtime

**Decision.** Keep SQLite + one `agent-supervisor` as the supported execution
runtime. `backend/app/distributed_queue.py` is a design contract only: no
external broker, no multi-host runtime, no claim of multi-host support.

**Evidence.** `docker-compose.yml` defines one `backend` and one
`agent-supervisor` sharing a single SQLite volume; `QueueCapabilities()` reports
`multi_host_supported=False`. No broker/scheduler dependency exists in
`backend/requirements.txt`.

**Consequences.** No multi-host integration test is claimed. Production must be
single-host unless a separate ADR authorizes a durable external store with
atomic claiming, leases, idempotency and recovery tests.

## ADR-002 — Market data is provenance-tagged and licenses are gated

**Decision.** Every market-data batch carries `status` (live / delayed /
historical / synthetic), `source`, `retrieved_at` and warnings
(`backend/app/market_data.py`). `backend/app/data_licensing_gate.py` blocks
unauthorized sources and keeps licensed providers pending manual review.
`backend/app/provider_health.py` reports freshness and local health without
calling any provider.

**Consequences.** The UI and reports must distinguish synthetic fixtures from
historical, delayed and live data. No live/delayed provider is activated until
license review and operator approval are recorded. No claim about current market
prices is permitted while only synthetic fixtures are active.

## ADR-003 — Imported execution code stays inert

**Decision.** AutoHedge signing/order modules, FinceptTerminal and Freqtrade
live-bot code remain reference-only. They are not imported, built, or executed
by the application. No wallet private keys, transaction signing, live order
routing or market-making execution exists.

**Consequences.** Health/diagnostics continue to report `broker_execution:
false`. Any future live-trading change requires a new ADR, security review and
explicit owner approval; it is out of scope for this mission.

## ADR-004 — Frontend verification uses the existing esbuild/React toolchain

**Decision.** Keep React 18 + TypeScript + custom esbuild build. Component/DOM
tests are added with Vitest + jsdom + Testing Library rather than migrating
build systems (Vite files were deliberately removed earlier).

**Consequences.** Existing `npm test` (node:test build-path utilities) remains
green alongside the new UI suite; `npm run build` remains the production build
authority.
