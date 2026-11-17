# MARKET-MIND-AI — Release Status

Last reviewed: 2026-11-17

## Current verified scope

The default branch contains a research-oriented FastAPI backend and a React/Vite frontend.

Implemented areas:
- Instrument reference search and local watchlist
- SQLite historical OHLCV storage, provenance, ingestion audit events, and data-lineage summaries
- CSV import and explicitly labelled synthetic fixtures
- Technical indicators, descriptive performance analytics, chart and multi-timeframe research reports
- Historical data-quality diagnostics and cross-source comparisons
- Reproducible evidence exports with SHA-256 digests
- Local workflow builder and research workspaces
- Private-by-default production Compose deployment with Nginx frontend proxy, internal-only API, persistent SQLite volume, health checks, browser security headers, resource limits, dropped Linux capabilities, and rotating container logs
- SQLite backup utility with integrity verification and SHA-256 digest
- Safe restore utility that verifies the source and restored database before atomic replacement, and refuses overwrite unless explicitly requested
- CI round-trip test for backup and restore inside the production API image
- Research-task concurrency regression coverage proving duplicate dispatch attempts cannot execute the same claimed task twice

## Verified operating constraints

- The configured provider status is `no_live_provider_configured`.
- The available adapter is a synthetic fixture, explicitly marked synthetic.
- Health/readiness responses set `paper_trading=false` and `broker_execution=false`.
- The backend provides no brokerage execution or order routing.
- `/api/ready` proves local database readiness only; it does not prove market data is available or current.
- Production deployment is intended to remain private. Optional shared bearer-token API authentication is implemented; individual identity and per-user role authorization are not implemented.

## Latest CI evidence

- Workflow run [43833086823](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/43833086823) for commit `7f56d372862370cb82c0f7cbbc4412b0ee53fa3e` passed all four jobs: backend compilation/unit tests/API and workflow smoke tests, frontend production build, Docker Compose integration smoke tests, and Python/frontend dependency audits.
- The backend job explicitly passed the complete discovered backend unit-test suite, including the new concurrent duplicate-dispatch regression test.
- Workflow run [41233993555](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41233993555) passed backend, frontend, dependency-audit, and production container build/start smoke checks after switching to unprivileged Nginx.
- Workflow run [41234005003](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41234005003) passed all four jobs, including the production proxy/API smoke test and backup/restore round-trip.
- Workflow run [41234313802](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41234313802) passed all four jobs after adding explicit assertions for loopback-only web binding, unpublished API port, dropped capabilities, `no-new-privileges`, non-root Nginx, and browser security headers.
- These CI checks validate the stack in GitHub Actions. They do not replace a host-specific deployment, restore drill, penetration test, or external security review.

## Remaining release work

| Workstream | State | Release gate |
|---|---|---|
| Local persistence and schema baseline | Implemented | Re-run clean-environment migration tests |
| Historical data provenance and audit | Implemented | Continue edge-case regression coverage |
| Research analytics and evidence export | Implemented | Re-run regression tests and inspect exported bundles |
| Frontend integration | Implemented in source | Maintain clean production-build verification |
| Live/delayed data provider | Not configured | Validate permissions, licensing, symbol mapping, freshness, and rate limits before enabling a provider |
| Private container packaging | CI build/start, proxy/API smoke, container isolation, and backup/restore integration passed | Verify persistence and recovery on the target Docker host |
| Backup and restore | Implemented and CI round-trip verified | Perform a host-specific restore drill and document retention/off-host storage |
| Public deployment security | Blocked | Add authentication/authorization, TLS ingress, request limits, and independent security review before public exposure |
| Operations | Partially implemented | Add observability, alerting, load tests, migration rollback, and incident procedures |
| Durable task execution | Partial | Replace process-local background dispatch with a durable queue and prove restart/recovery semantics |
| Agent intelligence | Partial | Add evidence-grounded retrieval/synthesis, isolated task context, benchmarked quality gates, and reviewed learning promotion |

## Recommended completion sequence

1. Replace process-local task dispatch with durable queueing and validate worker restart/recovery semantics.
2. Validate persistence and backup/restore on the intended private Docker host, including a recovery drill.
3. Add host-level observability, alerting, and representative load tests.
4. Add authentication/authorization and TLS ingress, followed by independent security review, before any public exposure.
5. Select and validate a properly licensed market-data provider before presenting non-synthetic data as current.
6. Implement evidence-grounded specialist research and benchmarked, reviewed learning before describing the system as autonomous or self-learning.
7. Record deployment environment, recovery results, and security review before calling the release complete.

## Scope boundary

This is a historical market-research and data-quality workspace. It does not provide brokerage connectivity, order placement, personalized investment recommendations, or guaranteed live market data. Keep execution disabled.


## Four-market architecture update — 2026-11-01

Implemented:
- Expanded the metadata-only instrument reference catalogue with explicit market groups: India, US, crypto and forex.
- Added stable internal reference identifiers, asset-class labels, instrument types, venue and quote-currency metadata.
- Added `market_group` filtering to `GET /api/instruments`, preserving the existing `market` asset-class filter.
- Added regression tests for all four market groups, metadata-only semantics and venue search.
- Added [Four-Market Platform Blueprint](docs/FOUR-MARKET-PLATFORM.md), covering canonical identifiers, historical event schemas, provider entitlements, data quality and staged implementation.

Not implemented by this update:
- No new live/delayed data connectors or provider credentials.
- No claim of complete exchange instrument coverage.
- No venue-aware global observation database migration yet; the existing OHLCV store retains its current symbol-based key.
- No CVD, footprint or order-book depth from OHLCV estimates.
- No broker integration, order routing or execution.

Verification:
- The previous quality-check workflow for commit `1b68619b9f87b7afb2a9c563812f0a5884298451` passed all four jobs.
- The 2026-11-16 quality-check workflow for commit `7f56d372862370cb82c0f7cbbc4412b0ee53fa3e` passed all four jobs, including the backend suite, frontend build, Compose integration smoke tests, and dependency audits.

## Operations and research-orchestration update — 2026-11-17

Implemented in the current default branch:
- Integrated exact source-excerpt citation auditing into the central research orchestration report and `POST /api/research/orchestrate`, including optional chunk hash and offset provenance checks. This verifies supplied-text traceability only; it does not prove source authenticity or semantic entailment.
- Added supervisor heartbeat persistence with process identity, polling configuration, heartbeat age, and explicit `not_started`, `starting`, `healthy`, `stale`, `failed`, and `stopped` health states on `GET /api/analytical-agent-supervisor/status`.
- Added a bounded GET-only API load probe at `scripts/load_check.py`, reporting throughput, status counts, p50/p95/max latency, and configurable error/latency thresholds. The Compose CI workflow invokes it against the readiness endpoint.
- Updated the roadmap and deployment guide to describe these capabilities and their operational limits.

Verification:
- Workflow run [44002649971](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44002649971) passed all jobs, including the bounded read-only API load probe, before the supervisor heartbeat changes.
- Workflow run [44028358662](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44028358662) is the current CI run for supervisor heartbeat changes. Backend, frontend, Trivy, and dependency-audit jobs have passed; Docker Compose integration was still running at the time of this status update.
- The heartbeat is process telemetry, not distributed leader election or guaranteed process liveness. SQLite remains a single-host queue. No host-specific deployment, real n8n instance, external security review, or provider setup is claimed complete.



## Security and worker-registry update — 2026-11-17

Implemented on the current default branch:
- Added optional deployment-wide API bearer authentication. It remains disabled for local development; when enabled, protected API requests require a high-entropy server-side token and fail closed if it is missing or misconfigured. Minimal health/readiness probes and CORS preflight remain available.
- Added automated middleware tests for disabled mode, missing server configuration, missing/invalid credentials, valid credentials, health/readiness exemptions, and CORS preflight.
- Documented the deployment token setup and its boundary: this is a shared API credential, not individual user identity or per-user role-based authorization. n8n reviewer/importer roles remain separate.
- Added per-worker lexical skill-alignment diagnostics using department/specialty and assigned skill metadata, with matched terms and zero-match worker reporting. This is explicitly a weak triage heuristic, not semantic evaluation or proof of capability.

Verification:
- Workflow run [44053846569](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44053846569) passed all five CI jobs, including backend tests, frontend build, dependency audit, Trivy scan, and Docker Compose integration (including n8n health/network and deployment checks).
- The lexical alignment change was included in run [44081788224](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44081788224), where the backend job initially failed at test-module import because of malformed continuation characters. Commit `7d8e1a34583a4dea5ef944c9f5a2eaa278da956c` fixed the test syntax. The follow-up run [44154131706](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44154131706) passed backend compilation, the full discovered backend unit-test suite and API smoke test; frontend build, Trivy and Docker Compose integration also passed.
- The API token must be generated and configured on the target host; no user secret has been requested or committed.

Remaining:
- Individual identity and scoped roles, TLS ingress and independent security review.
- Human review and task-level benchmark validation of worker/skill suitability.
- Host-specific deployment acceptance, backup restore drill, licensed data provider configuration, and n8n instance acceptance remain external setup/review tasks.


## Benchmark and review-gate clarification — 2026-11-18

Implemented in source and covered by focused unit tests:
- Offline research traceability benchmark with an explicit allowlist of three structural metrics, baseline schema validation, deterministic fixture fingerprinting, per-metric compared/skipped states, and regression/incomplete-comparison summaries. Skipped metrics are not counted as passing.
- Versioned, content-hashed benchmark records with SQLite persistence and integrity re-verification on retrieval.
- Reviewed promotion-decision records linked to benchmark evidence. Approval is blocked when a baseline is absent, comparisons are incomplete, regression evidence is inconsistent, or the benchmark record fails integrity checks. Decisions are recorded for audit; they do not modify active configuration or deploy changes.
- These are structural research-quality controls over caller-supplied fixtures, not factual-accuracy, forecasting, market-performance, or model-learning proof.

Verification status:
- The latest workflow run [44081788224](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44081788224) passed frontend, dependency audit, Docker Compose integration and Trivy; backend failed on the test-file syntax issue described above.
- Commit `7d8e1a34583a4dea5ef944c9f5a2eaa278da956c` fixes the two malformed test lines. A fresh workflow result is still required before marking the backend suite green.
- Durable distributed task queue/restart recovery, per-user identity/authorization, task-level specialist benchmarks, host-specific restore and security acceptance remain outstanding.
- The follow-up run's dependency-audit job still fails on four high-severity frontend dependency findings involving picomatch through Vite's fdir/tinyglobby chain. The current GitHub advisory identifies picomatch versions through 4.0.7 as affected and does not list a patched version. Do not silence the audit or force a potentially breaking downgrade; re-evaluate when an upstream fixed release is available.


## CI verification update — 2026-11-18

Workflow run [44154131706](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44154131706) results:
- Backend: passed, including compile, unit tests and API runtime smoke test.
- Frontend: passed production build.
- Trivy filesystem security scan: passed.
- Docker Compose integration: passed, including proxy/readiness checks, bounded GET-only load probe, optional n8n startup/health/network checks and portable deployment verification.
- Dependency audit: backend Python audit passed; frontend npm audit failed on four high-severity findings associated with picomatch via the Vite dependency chain.

Security handling:
- Advisory GHSA-fc5q-39xc-vjpf (CVE-2026-112366) identifies picomatch through 4.0.7 as affected. At this review, the advisory does not state a patched version. The finding remains visible and the audit gate remains enabled; no vulnerability suppression or unverified override has been added.
- A clean full CI run is therefore not yet achieved despite the backend and integration checks passing.
