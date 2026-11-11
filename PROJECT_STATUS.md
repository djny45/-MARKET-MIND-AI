# MARKET-MIND-AI — Release Status

Last reviewed: 2026-11-11

## Current verified scope

The default branch contains a research-oriented FastAPI backend and a React/Vite frontend. This status distinguishes code on `main` from work that is still in an open pull request.

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

## Current authentication work — PR #30 (not merged)

Pull request [#30 — Add authentication cryptographic primitives](https://github.com/djny45/-MARKET-MIND-AI/pull/30) adds dependency-free scrypt password hashing and verification, random session/CSRF token generation, session-token hashing, constant-time comparisons, and focused unit tests.

The latest observed GitHub Actions run for PR #30, [43028279674](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/43028279674), completed successfully. This is evidence for that pull-request revision and workflow only; it is not a verification of a merged release or a host deployment.

**Authentication is not complete.** PR #30 does not add persistent session storage, login/logout endpoints, route authorization, CSRF middleware, origin validation, rate limiting, frontend login integration, or independent security review. Keep the service private and do not describe these helpers as a complete authentication system.

## Analytical-worker scope

The repository contains 550 registered analytical-worker identities and bounded task/memory/review APIs. This does not mean 550 independent, continuously running autonomous agents. Task dispatch currently uses process-local FastAPI background work; it is not a durable distributed queue or cloud scheduler. Memory candidates and improvement proposals require explicit human review and do not autonomously train model weights, change strategies, or deploy code.

## Verified operating constraints

- The configured provider status is `no_live_provider_configured`.
- The available adapter is a synthetic fixture, explicitly marked synthetic.
- Health/readiness responses set `paper_trading=false` and `broker_execution=false`.
- The backend provides no brokerage execution or order routing.
- `/api/ready` proves local database readiness only; it does not prove market data is available or current.
- Production deployment is intended to remain private; authentication and per-user authorization are not yet complete on `main`.

## Latest CI evidence

- Workflow run [41233993555](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41233993555) passed backend, frontend, dependency-audit, and production container build/start smoke checks after switching to unprivileged Nginx.
- Workflow run [41234005003](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41234005003) passed all four jobs, including the production proxy/API smoke test and backup/restore round-trip.
- Workflow run [41234313802](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41234313802) passed all four jobs after adding explicit assertions for loopback-only web binding, unpublished API port, dropped capabilities, `no-new-privileges`, non-root Nginx, and browser security headers.
- PR #30's latest observed workflow run is listed above; it must still be reviewed and merged before its changes become part of `main`.
- These CI checks validate the stack in GitHub Actions. They do not replace a host-specific deployment, restore drill, penetration test, or external security review.

## Remaining release work

| Workstream | State | Release gate |
|---|---|---|
| Local persistence and schema baseline | Implemented | Re-run clean-environment migration tests |
| Historical data provenance and audit | Implemented | Continue edge-case regression coverage |
| Research analytics and evidence export | Implemented | Re-run regression tests and inspect exported bundles |
| Frontend integration | Implemented in source | Maintain clean production-build verification |
| Live/delayed data provider | Not configured | Validate permissions, licensing, symbol mapping, freshness, and rate limits before enabling a provider |
| Authentication cryptographic primitives | In PR #30 | Review and merge only after code review and required checks |
| Complete authentication and authorization | Not implemented | Add session persistence, login/logout, expiry/revocation, route authorization, CSRF/origin enforcement, rate limiting, and frontend integration |
| Private container packaging | CI build/start, proxy/API smoke, container isolation, and backup/restore integration passed | Verify persistence and recovery on the target Docker host |
| Backup and restore | Implemented and CI round-trip verified | Perform a host-specific restore drill and document retention/off-host storage |
| Public deployment security | Blocked | Complete authentication/authorization, TLS ingress, request limits, and independent security review before public exposure |
| Operations | Partially implemented | Add observability, alerting, load tests, migration rollback, and incident procedures |

## Recommended completion sequence

1. Review and merge PR #30 only after its complete diff and required checks have been reviewed.
2. Implement and test persistent sessions, login/logout, route authorization, CSRF/origin checks, rate limits, and frontend integration as a separate change.
3. Validate persistence and backup/restore on the intended private Docker host, including a recovery drill.
4. Add host-level observability, alerting, and representative load tests.
5. Select and validate a properly licensed market-data provider before presenting non-synthetic data as current.
6. Complete TLS ingress and independent security review before any public exposure.
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
- New commits in this four-market update require their own CI run before being considered verified.
