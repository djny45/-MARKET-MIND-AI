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
- Production deployment is intended to remain private. Optional shared bearer-token API authentication is implemented, and per-user sessions (deployment opt-in: scrypt passwords, HttpOnly session cookies, hashed CSRF, idle/absolute expiry, `viewer/analyst/operator/admin` roles, login/logout/me) are implemented and tested; full per-resource authorization, TLS ingress, and independent security review remain outstanding.

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
| Durable task execution | Implemented on a single host | Validate supervisor restart/recovery on the target Docker host |
| Agent intelligence | Partial | Add evidence-grounded retrieval/synthesis, isolated task context, benchmarked quality gates, and reviewed learning promotion |

## Recommended completion sequence

1. Validate the existing single-host durable queue and supervisor restart/recovery semantics on the target Docker host.
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
- A durable single-host SQLite queue with supervisor restart/recovery is implemented. Per-user sessions (password auth, CSRF, roles, login/logout/me), opt-in rate limiting, and the licensed-data access gate are implemented and tested.
- Research-loop engine is complete: drift/regime detection, skill-promotion engine, shadow tracker with ten-cycle demotion, 24-hour shadow rule, and skill-generation/validation cadence are all merged and CI-green (HEAD `6349230`).
- Trivy CI: `.github/workflows/trivy-fs.yml` is committed locally but not pushed — the OAuth app refuses workflow-file changes without `workflow` scope. Run Trivy locally with `trivy fs --scanners misconfig,secret --severity MEDIUM,HIGH,CRITICAL .` and review any findings.
- Distributed multi-host queue: design contract implemented (`backend/app/distributed_queue.py`), runtime is not yet implemented.
- Distributed multi-host queueing, full per-resource authorization, TLS ingress, task-level specialist benchmarks, host-specific restore and security acceptance remain outstanding.
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


## API authentication regression verification — 2026-11-18

Latest default-branch authentication hardening:
- Commit `2aabcc9050aeb0314013d98d5ff1bac622768dc1` rejects duplicate Authorization headers and strictly validates bearer-token formatting.
- Commit `5646db8eb3d19527f449648a8d3f16f4d923db93` adds regression tests for duplicate headers, malformed/whitespace-padded values, and case-insensitive Bearer scheme parsing.

Verification: workflow run [44160909195](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44160909195) completed. Backend tests, frontend production build, Docker Compose integration (including proxy/readiness, bounded GET-only load probe, optional n8n health/network checks, and deployment verification), and Trivy filesystem scan passed. The dependency-audit job failed only at the frontend npm audit step because the existing high-severity picomatch findings remain unresolved; the backend Python dependency audit passed. The audit gate remains enabled and findings are not suppressed.

This CI run verifies the authentication regression changes on the default branch. It does not establish a clean all-green pipeline, host-specific deployment acceptance, or external security approval.


## Follow-up CI investigation — 2026-11-18

Workflow run [44273459114](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44273459114), triggered by the status-documentation commit, completed with:
- Backend compilation, unit tests and API smoke tests: passed.
- Frontend standalone production build: passed.
- Trivy filesystem scan: passed.
- Frontend dependency audit: failed on the already-recorded high-severity picomatch findings; backend Python audit passed.
- Docker Compose integration: failed during the frontend image build. The container build's Vite/Rollup CommonJS resolver reported `Code is nested too deeply` while parsing `react-dom/client.js`; later proxy, load-probe, n8n and deployment checks were skipped because the image did not build.

This is a separate reproducibility/build-context issue from the npm audit finding. The standalone CI frontend build passing does not establish that the Docker image build is healthy. Investigate the container build environment and dependency resolution before changing build flags or weakening checks. Keep both blockers visible until a clean run verifies the fix.


## Frontend build-toolchain remediation — 2026-11-18

Changes committed for CI verification:
- Replaced Vite and `@vitejs/plugin-react` with esbuild 0.28.2, removing the Vite → tinyglobby/fdir → picomatch dependency path from the declared frontend toolchain rather than suppressing the advisory.
- Added esbuild production and watch-mode development scripts. The production build type-checks with TypeScript, bundles the React entry point and imported CSS, copies the application shell and existing public HTML assets, and substitutes the configured API URL at build time.
- Updated the frontend HTML shell to load the generated JavaScript and CSS assets.
- Changed the frontend Docker build stage from Alpine to Debian slim to align the container's Node runtime/libc family more closely with the Ubuntu CI build environment, reducing platform-specific native bundler differences.

Verification: workflow run [44275092002](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44275092002) passed all five jobs after these changes. The frontend TypeScript/esbuild production build passed; the frontend and backend dependency audits passed; the Trivy filesystem scan passed; and Docker Compose built and started the private stack, passed API/frontend proxy checks, the bounded GET-only load probe, optional n8n health/network checks, and portable deployment verification. The previous picomatch advisory no longer appears in the audited dependency graph because the Vite toolchain that introduced that dependency path was removed; the audit gate itself remains enabled and unchanged. The Docker build now uses Debian slim rather than Alpine, and the Compose image build plus runtime checks passed.

## Research queue recovery concurrency regression — 2026-11-18

Added a two-thread regression test that starts simultaneous stale-task recovery calls against the same interrupted SQLite task. The test asserts that only one caller requeues the task, only one task_requeued audit event is written, the execution-attempt count is preserved, and the stale execution token is cleared. This exercises the existing BEGIN IMMEDIATE serialization and conditional status transition rather than changing queue semantics.

Verification:
- The regression test was committed in 67d8b3817e5ed327c836f45eaf707d1c2cb0d0c6; CI exposed two test-fixture/assertion issues, corrected in 421c8c1309b0e733ccce10d603c494df46b4d825 and f29b353a53656d3d80ac07786d3fd98e57631a76.
- Workflow run [44277109570](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/44277109570) for the corrected test passed all five jobs: backend (869 tests), frontend, dependency audit, Trivy filesystem scan, and Docker Compose integration.
- The regression verifies concurrent recovery serialization and exactly-once requeue auditing. It does not turn the SQLite queue into a distributed broker or replace host-level restart/recovery drills.

## Supervisor shutdown and startup-recovery regression — 2026-11-18

Added two lifecycle tests to the analytical-agent task suite:
- Graceful stop: a stop signal raised during a polling cycle allows that cycle to finish, prevents another cycle, and records the final `stopped` heartbeat.
- Fail-closed startup: if stale-task recovery raises an exception, the supervisor records a sanitized `failed` heartbeat and exits without dispatching queued tasks.

Verification: commit `0e5a75d6ecd4e1ae461851fd0d9e6a5c3a3752a4` passed workflow run [44280558763](https://github.com/dj45/-MARKET-MIND-AI/actions/runs/44280558763) across all five jobs: backend, frontend, dependency audit, Trivy filesystem scan, and Docker Compose integration. This validates the supervisor's tested shutdown and startup-failure behavior; it does not replace a host-level process-kill, persistent-volume backup, or restore drill.

