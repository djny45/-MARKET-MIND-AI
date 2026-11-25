# Phase 3 Operational Readiness Audit

**Audit date:** 2026-11-26  
**Repository:** `djny45/-MARKET-MIND-AI`  
**Audit branch:** `phase3-operational-readiness-audit`  
**Parent candidate commit:** `f4ea61aa7cf24305c27d419ec7851a07a525541e`  
**Previously declared verified baseline:** `b47781aa3df633f9bc969221633e543d28ac877c`  
**Decision:** **CONDITIONAL / NOT FULLY OPERATIONAL**

This is a documentation-only audit branch. It does not alter the verified baseline, application code, open PRs, deployment configuration, or running services.

## 1. Repository and CI state

- PR #107 is open and unmerged: https://github.com/djny45/-MARKET-MIND-AI/pull/107
- PR head: `feature/alpine-backend-runtime`
- PR base: `feature/phase5-risk-resolution`
- Exact remote head inspected: `f4ea61aa7cf24305c27d419ec7851a07a525541e`
- The GitHub connector returned two successful Vercel status checks for that SHA, but no GitHub Actions workflow runs. Therefore, the latest UAT-fix head is **not independently CI-verified by this audit**.
- The earlier baseline `b47781aa` is not the current PR head. Do not treat its earlier reported CI result as proof that `f4ea61aa` passed the same checks.

## 2. LLM provider configuration

### Existing implementation found

The backend already has an environment-driven shared intelligence core:

```dotenv
INTELLIGENCE_CORE_ENABLED=false
INTELLIGENCE_CORE_PROVIDER=mercury
INCEPTION_API_KEY=
INCEPTION_MODEL=mercury-3
```

Relevant implementation and documentation:

- `backend/app/mercury_adapter.py` reads `INCEPTION_API_KEY` only from the backend process environment and sends it as a Bearer authorization header to the fixed HTTPS Mercury endpoint.
- `backend/app/intelligence_core.py` reports configuration state without making a network request and has bounded provider-failure handling.
- `docs/FREELLMAPI-INTEGRATION.md` documents enabling Mercury and keeping the key in an untracked private environment file or secret manager.
- `backend/tests/test_intelligence_core.py` contains provider configuration and safe-fallback tests, including a Mercury adapter test.

### Operator configuration template

Set these only in the backend's private environment or secret manager, never in frontend variables, Git, notebooks, screenshots, logs, or public issues:

```dotenv
INTELLIGENCE_CORE_ENABLED=true
INTELLIGENCE_CORE_PROVIDER=mercury
INCEPTION_API_KEY=<operator-supplied-secret>
INCEPTION_MODEL=mercury-3
```

The key is intentionally not included in this report. After configuration, restart the backend and check `GET /api/intelligence-core`. That endpoint reports configuration; it does **not** prove that the key is valid, that quota is available, or that the provider is reachable. A real provider request and safe-fallback check must be run by the operator without recording the key or authorization header.

**Current status:** configuration interface exists in source, but the checked-in template has the core disabled and the key blank. No operator key or successful live provider call was available to this audit. LLM activation is therefore **prepared, not operationally verified**.

The LLM is a bounded synthesis layer over supplied research artifacts. It must not be represented as the market-data source, a deterministic calculation engine, autonomous model training, or an order-execution system.

## 3. Market-data provider architecture and live-feed findings

### Existing data contract

`backend/app/market_data.py` defines normalized OHLCV batches with:

- timezone-aware bar timestamps;
- provider/source identifier;
- status: `live`, `delayed`, `historical`, or `synthetic`;
- UTC retrieval timestamp;
- warnings and validation of numeric values, OHLC envelope, timestamp ordering, and duplicates.

The stored market-data layer retains source, status, bar timestamp, and retrieval timestamp. Synthetic fixtures are explicitly labelled and must never be presented as market prices.

### Live feed script found

`scripts/live_market_feed.py` currently contains a public Binance klines ingester:

- public REST endpoint; no API credential and no broker order calls;
- four crypto symbols (BTC, ETH, SOL, BNB);
- 15-minute candles, up to 120 bars per request;
- polling interval of 60 seconds;
- source label `binance-public`;
- records exchange bar timestamps and a UTC `retrieved_at` value;
- includes a warning that redistribution is not licensed.

This proves that a live-feed script exists in the branch. It does **not** prove that the script is running in the user's environment, that a live feed is currently connected, or that the source is approved for the intended use.

### Blocking integration and provenance issues

1. The script hardcodes `/home/jovyan/-MARKET-MIND-AI/backend` in `sys.path`, so it is not portable to another checkout path.
2. The script docstring says live status requires operator attestation through `MARKET_MIND_ATTESTED_DATA_SOURCES`, but the script itself does not call the attestation validator before writing a `LIVE` batch.
3. `backend/app/market_store.py::store_batch` persists a batch without enforcing the licensing/attestation gate. The API route's gate therefore must not be assumed to protect this direct script path.
4. `docs/MARKET_DATA_LICENSING.md` says no licensed live/delayed provider is configured and that `MARKET_MIND_ATTESTED_DATA_SOURCES` is empty by default.
5. The licensing document requires provider terms, caching/redistribution limits, attribution requirements, and written operator approval before enabling a live/delayed source. The ingester itself warns that Binance data is not licensed for redistribution.
6. The checked-in `backend/.env.example` does not currently document `MARKET_MIND_ATTESTED_DATA_SOURCES` or a managed live-feed service configuration.

**Required before operational live-data activation:** make the ingester use a portable project-relative path; enforce the same source-attestation/licensing gate in every ingestion path, including direct script writes; add explicit feed configuration and service lifecycle/health reporting; add tests for missing attestation, rejected sources, stale data, provider errors, timestamps, and redaction; and complete operator review of the source's terms for the intended internal display/use. Do not set a source to approved merely to make the feed appear live.

Until these are done, keep synthetic fixtures visibly labelled and treat the Binance script as an unverified integration candidate, not an approved production feed.

## 4. Agent inventory, skills, memory, and research workflow

Repository source supports the following bounded architecture:

- `backend/app/workers.py` generates 550 worker/agent profiles.
- `backend/app/worker_registry.py` validates the expected count, IDs, unique memory namespaces, and allowed skill references.
- `backend/tests/test_worker_registry.py` includes registry-count, profile-metadata, memory-namespace, and skill-reference validation tests.
- The README describes one shared intelligence core, distinct per-profile role/context and memory namespaces, and bounded task execution.
- Worker memory is an append-only evidence-note store. It is not model-weight training, automatic prompt injection, or independent verification of stored claims.

**Important capability boundary:** 550 registered profiles/templates are not 550 independently running foundation models or 550 continuously autonomous agent processes. The documented runtime is bounded and delegated; single-host SQLite queue behavior does not establish distributed/cloud execution.

### UAT evidence status

The operator-provided OpenCode UAT screenshots report:

- 46/46 API checks passed;
- 20/20 browser modules reopened;
- 550/550 profiles visible and 1,290 graph connections;
- 1,331 backend tests and 131 frontend UI tests green after the authentication fix.

These are recorded here as **operator-reported local results**, not independently rerun or reproduced by the GitHub read-only audit. The UAT report and its 22 screenshots were described as local/uncommitted in the screenshot; they were not found at the repository root on the earlier baseline.

A final UAT run should separately exercise representative agent task submission, queue dispatch, memory write/read ownership, skill resolution, research provenance, LLM-disabled fallback, and LLM-enabled synthesis using a test credential. Do not infer all-agent task execution from profile visibility alone.

## 5. Trading and execution boundary

The checked-in paper-trading subsystem is virtual:

- `backend/app/paper_trading/config.py` describes 550 virtual portfolios and a virtual capital allocation.
- `backend/app/paper_trading/live.py` reads already-stored market bars and simulates virtual orders; its own module documentation says it has no live exchange connection.
- `backend/app/paper_trading/api.py` reports `broker_execution: false`.
- The paper loop can be disabled with `MM_PAPER_ENABLED=false`.

**This project remains research and simulation only.** No real-money brokerage execution, wallet key handling, transaction signing, autonomous live orders, or market-making is to be implemented or enabled. Keep broker execution disabled permanently; live market-data ingestion is separate from order execution.

## 6. Phase 3 acceptance table

| Workstream | Evidence found | Status |
|---|---|---|
| Exact current commit / PR state | PR #107 open; head `f4ea61aa...` | Verified remotely |
| Latest-head GitHub Actions CI | No workflow runs returned; only two successful Vercel statuses | **Unverified** |
| LLM environment configuration | Mercury env vars, adapter, docs, tests exist | Prepared; key/provider call not configured or verified |
| Secret handling | Backend-only environment key path; docs prohibit committing/exposing keys | Source-reviewed; runtime log scan not run |
| Market-data contract/provenance | Source, status, timestamps, warnings and validation exist | Source-reviewed |
| Live public-feed script | Binance public klines script exists | Present; not proven running or licensed for intended use |
| Feed attestation enforcement | Direct script/store path does not enforce attestation | **Blocker** |
| Feed portability/service lifecycle | Hardcoded Jupyter path; no managed service evidence | **Blocker** |
| 550 profiles / skills / memory namespaces | Registry implementation and tests found; local UAT screenshot reports 550/550 | Source-supported; latest-head tests not independently rerun |
| Agent task coordination | Bounded task/queue architecture documented | Needs latest-head runtime UAT |
| Real-money execution | Paper subsystem explicitly reports broker execution false | Excluded; keep disabled |

## 7. Required next actions

1. Fix the live-feed attestation bypass and hardcoded path; add regression tests. Do not claim a provider is authorized without operator evidence.
2. Add explicit environment documentation for approved source IDs, feed symbols/interval/polling, and a safe disabled-by-default service lifecycle.
3. Run the live-feed integration only after operator licensing/terms review; verify source, exchange timestamp, retrieval timestamp, staleness, error handling, and attribution in the UI.
4. Configure Mercury only when the operator supplies a key directly to the private backend environment. Test success, timeout, invalid-key, and safe fallback without logging secrets.
5. Re-run registry, skill, memory, research workflow, and agent-task tests on the exact Phase 3 commit.
6. Run the complete backend/frontend/build/security CI on the exact latest commit and retain links to the run and artifacts.
7. Update the UAT report with the exact commit SHA and mark local versus CI evidence separately.

## 8. Verification limits

This audit used GitHub repository/commit/PR/file reads. It did not execute code, access the Jupyter runtime, inspect the operator's environment variables, call Binance or Mercury, validate provider terms, run tests, inspect runtime logs, or verify a running service. No secret was requested or recorded.

No application source was modified by this audit. No PR was merged, no deployment was triggered, no legacy file was deleted, and no real-money trading capability was added.
