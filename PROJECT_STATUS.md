# MARKET-MIND-AI — Release Status

Last reviewed: 2026-11-07

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

## Verified operating constraints

- The configured provider status is `no_live_provider_configured`.
- The available adapter is a synthetic fixture, explicitly marked synthetic.
- Health/readiness responses set `paper_trading=false` and `broker_execution=false`.
- The backend provides no brokerage execution or order routing.
- `/api/ready` proves local database readiness only; it does not prove market data is available or current.
- Production deployment is intended to remain private; no authentication or per-user authorization is implemented.

## Latest CI evidence

- Workflow run [41233993555](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41233993555) passed backend, frontend, dependency-audit, and production container build/start smoke checks after switching to unprivileged Nginx.
- Workflow run [41234005003](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41234005003) passed all four jobs, including the production proxy/API smoke test and backup/restore round-trip.
- Workflow run [41234313802](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/41234313802) passed all four jobs after adding explicit assertions for loopback-only web binding, unpublished API port, dropped capabilities, `no-new-privileges`, non-root Nginx, and browser security headers.
- These CI checks validate the stack in GitHub Actions. They do not replace a host-specific deployment, restore drill, penetration test, or external security review.

## Open-source self-evolution intake — 2026-11-08

Implemented on the open PR branch:
- Added a guarded GitHub repository URL normalizer and open-source intake plan builder.
- Added `POST /api/open-source/intake` to create an auditable review checklist for a candidate repository.
- Added unit and API tests for URL validation, request bounds, license review gates, and default-deny reuse/execution/merge behavior.
- Added [Self-Evolving Architecture](docs/SELF-EVOLUTION-ARCHITECTURE.md) with milestones for crawling, reverse-engineering, skill learning, self-building, adaptation, and rollback.

Important limitation:
- This increment is **intake planning only**. It does not crawl/fetch GitHub, clone repositories, copy code, execute third-party scripts, learn model weights, or autonomously merge changes.
- Repository license text still requires review; an SPDX label alone is not authorization.
- Current-head CI and tests are unverified until a workflow run reports results.

## GitHub metadata crawler increment — 2026-11-08

Implemented on the open PR branch:
- Added a bounded, metadata-only GitHub REST crawler with a fixed API host, validated repository URL, disabled redirects, response-size limit, and commit SHA validation.
- Added `POST /api/open-source/crawl-metadata` to retrieve repository metadata and pin the default-branch commit.
- Added crawler unit tests and API contract tests for URL rejection, redirects, oversized responses, invalid SHAs, and upstream failure handling.
- Updated the self-evolution architecture milestones.

Limitations: this is not yet a full source crawler. Repository tree enumeration, README/dependency file retrieval, license/NOTICE text capture, caching/rate-limit backoff, and static reverse-engineering are still pending. Tests are committed but not run in this environment; current-head CI is not yet verified.

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

## Recommended completion sequence

1. Validate persistence and backup/restore on the intended private Docker host, including a recovery drill.
2. Add host-level observability, alerting, and representative load tests.
3. Add authentication/authorization and TLS ingress, followed by independent security review, before any public exposure.
4. Select and validate a properly licensed market-data provider before presenting non-synthetic data as current.
5. Record deployment environment, recovery results, and security review before calling the release complete.

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

## OpenBB research integration update — 2026-11-05

Implemented on the open PR branch:
- Added an isolated OpenBB CLI setup script and import-verification script.
- Hardened setup cleanup so failed installation does not leave a partial virtual environment.
- Improved the import verifier's Git-tracking check.
- Documented Windows Python interpreter selection and ignored the local `.venv-openbb/` directory.
- Restricted the API adapter to informational CLI actions; this is not a public shell or an unrestricted interactive terminal.

CI:
- The earlier Version 3.4 quality-check pass applies to an older commit, not the current PR head.
- No workflow run was returned for the latest PR head during this audit; current-head CI is unverified.
- Check [PR #4](https://github.com/djny45/-MARKET-MIND-AI/pull/4) for the live head SHA and CI status.
- PR #4 remains open and unmerged.

Not yet completed:
- The full upstream OpenBB repository has not been imported into `vendor/openbb`.
- Import verification has not been run against a completed subtree checkout.
- OpenBB providers, credentials, and live data access have not been validated.
- The current frontend OpenBB panel is an informational restricted command panel, not a full interactive terminal.

Do not describe OpenBB as fully integrated or live-data-ready until these gates are completed.
## Historical research integrity update — 2026-11-07

Implemented on PR #4:
- Swing-point timeline annotations now appear at their confirmation bars, with pivot and confirmation timestamps kept separately.
- Timeline timestamps are validated as timezone-aware, unique and chronological; regression tests include prefix stability.
- Offline CSV research hashes and parses the same byte snapshot; export rejects source changes after research.
- Blank optional CSV metadata is converted to JSON null before strict evidence serialization.
- Indicator calculations use scaled arithmetic to reduce overflow in finite-value SMA, Bollinger and volatility inputs.
- SMC and TA-Lib adapters share OHLC normalization and validation; optional dependencies remain isolated.
- OpenBB import is pinned to a reviewed upstream commit; CLI version lookup uses the interpreter beside the CLI executable.
- Dispatch status/audit handling and supervisor stale-threshold validation received regression coverage.

Verification:
- Added `.github/workflows/backend-tests.yml` to run the backend unittest suite on PRs and this branch.
- GitHub workflow lookup returned no run for the workflow commit yet; execution remains unverified.
- Tests were not run locally in this environment. Do not mark this update CI-verified until a workflow or local test run completes.


## Additional numerical and adapter audit — 2026-11-07

Latest PR-branch changes:
- Restored explicit TA-Lib period validation after extracting common OHLC validation.
- Added SMC validation for positive integer swing length and finite, normalized liquidity range.
- Removed duplicate validation blocks introduced during the refactor.
- Stabilized EMA weighted arithmetic against intermediate overflow and added finite-output guards for MACD.
- Added a maximum-float EMA regression test.
- Fixed the OHLC timeline regression fixture so it isolates the intended high/open/close violation.

Verification:
- GitHub workflow lookup returned no runs for the latest adapter/indicator commits.
- No local test execution was available; these changes remain unverified until backend CI or a local test run completes.


## Historical forecasting solver audit — 2026-11-07

- Added shape and alignment checks for ridge training inputs.
- Rejects boolean, non-finite, and oversized numeric inputs for features, targets, alpha, and linear-system values.
- Added finite coefficient checks after Gaussian elimination.
- Added regression tests for malformed matrices, non-finite values, invalid alpha, ragged feature rows, and huge Python integers.

Verification:
- GitHub Actions workflow lookup returned no runs for these latest commits.
- Tests are not locally executed; the changes remain unverified pending CI.


## Forecast metric and walk-forward edge-case audit — 2026-11-07

- Forecast metric subtraction now normalizes overflow to a clear validation error.
- Walk-forward aggregation uses stable summation and rejects non-finite aggregate metrics.
- Added regression tests for extreme subtraction and overlapping walk-forward test windows.

Verification:
- GitHub Actions lookup returned no runs for the latest forecasting commits.
- No local tests were executed; verification remains pending.


## Ridge prediction validation audit — 2026-11-07

- Added feature/coefficient dimensionality checks to the ridge predictor.
- Predictor rejects non-finite inputs and overflowed predictions instead of returning invalid forecast values.
- Added regression coverage for mismatched feature widths and prediction overflow.

Verification:
- No GitHub Actions workflow runs were returned for the latest commits.
- Tests have not been executed locally; validation remains pending CI.


## Walk-forward numerical aggregation audit — 2026-11-07

- Validation MAE selection now uses `math.fsum` and rejects non-finite scores in both walk-forward implementations.
- Pre-test mean-return baselines now use finite-checked compensated summation.
- Legacy walk-forward per-window aggregation now checks overflow and non-finite aggregate metrics.
- Both public walk-forward APIs remain available; their historical split/report differences are preserved for compatibility.

Verification:
- No local test execution available in this environment.
- GitHub Actions status will be checked for the latest commits; do not treat the code as verified until CI runs.


## Yahoo historical adapter integrity audit — 2026-11-07

- Yahoo's requested 4h interval now aggregates only complete, UTC-aligned four-hour groups from hourly bars; incomplete groups are discarded instead of being mislabeled as 4h candles.
- The adapter rejects duplicate or out-of-order retained timestamps, protecting downstream chronological research from accidental time leakage.
- Four-hour aggregate volume uses finite-checked `math.fsum`; overflow is normalized to a clear validation error.
- Added regression coverage for aggregation fields, incomplete groups, and timestamp ordering.

Verification:
- Tests were authored/updated but not executed locally.
- GitHub Actions status is checked after these commits; absent runs mean this remains unverified.


## GitHub repository tree scanner increment — 2026-11-08

Implemented on the open PR branch:
- Added a pinned GitHub tree scanner that fetches the recursive Git tree for the commit SHA returned by the metadata crawler.
- Added basic path classification for source-language files, README/docs, license/NOTICE filenames, GitHub configuration and dependency-manifest filenames.
- Added `POST /api/open-source/scan-tree`, returning a bounded manifest (maximum 20,000 entries) and explicit scanner policy.
- Rejects truncated tree responses instead of reporting an incomplete repository inventory as complete; submodules are recorded as references only.
- Added unit and API tests for classification, commit pinning, URL rejection, truncation, entry limits and upstream errors.

Limitations:
- This scans paths and Git object metadata only. It does not fetch README, license, NOTICE, dependency or source file contents; dependency versions and source architecture are not yet analyzed.
- No repository code is copied, installed or executed. Tests are committed but not run in this environment; current-head CI is unverified.


## Allowlisted repository review-file retrieval — 2026-11-08

Implemented on the open PR branch:
- Added a pinned-SHA file retrieval stage for allowlisted README, license/NOTICE and dependency-manifest names only.
- Enforced a 64 KB per-file cap, 256 KB aggregate cap, 12-file cap, and bounded GitHub API responses.
- Added SHA-256 hashes and repository blob SHAs to retrieved text records; skips non-UTF-8 files.
- Added `POST /api/open-source/scan-review-files` and regression tests for content decoding, path matching, allowlist enforcement, size limits and API error handling.

Limitations:
- This does not retrieve arbitrary source files, install dependencies, execute repository code, or automatically approve licenses.
- README, license, NOTICE and manifest text is untrusted. License/NOTICE review and dependency vulnerability/compatibility analysis remain manual/pending.
- Tests are committed but not executed in this environment; current-head CI remains unverified.
