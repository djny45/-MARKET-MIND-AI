# MARKET-MIND-AI — Phase 2 User Acceptance Test Report

**Baseline:** `b47781aa3df633f9bc969221633e543d28ac877c` (verified commit, unchanged)
**Date:** 2026-11-25
**Scope:** live backend + frontend from a clean detached worktree at the exact baseline; research-only, paper simulation only. No real-money trading, wallet signing, broker order execution, merge, deploy, deletion of legacy files, or modification of the verified baseline was performed.

## Summary (actual results, not estimates)

| Category | Result |
| --- | --- |
| Authenticated API endpoint checks | **46 passed / 0 unexpected failures** (2 intentional error probes returned the expected 401/400) |
| Terminal modules opened in a real browser | **20 / 20 opened**; 20 screenshots captured |
| Research workflow (route → queue → dispatch → complete → audit) | **PASS** |
| 550-agent inventory consistency | **PASS** (5 independent endpoints all report 550) |
| Memory, skills, learning feedback | **PASS** |
| Live research dashboard / API connectivity | **PASS** (banner CONNECTED; signed in as admin) |
| Market-data pipeline | **PASS with limitation** (synthetic fixture only; 0 stored bars; no live provider) |
| Backend 5xx / tracebacks during UAT | **0 / 0** |
| Known defects found | **2** (frontend credential omission; agent-network graph empty) |
| Overall UAT verdict | **CONDITIONAL PASS** — core research/paper functionality works; 2 UI defects to fix before full sign-off |

## 1. Setup (exact)

A clean worktree was created at the verified baseline so the main worktree and its uncommitted user work were untouched:

```bash
git worktree add --detach /tmp/opencode/uat b47781aa3df633f9bc969221633e543d28ac877c
ln -s /home/jovyan/-MARKET-MIND-AI/frontend/node_modules /tmp/opencode/uat/frontend/node_modules
# backend (own fresh DB, auth enabled, scoped CORS)
MARKET_MIND_DB=/tmp/opencode/uat-data/market_mind.db PYTHONPATH=backend \
MARKET_MIND_USER_AUTH=true MARKET_MIND_USERS=<hashed-test-users> \
FRONTEND_ORIGINS=http://127.0.0.1:15190 \
  .venvs/backend/bin/uvicorn app.main:app --host 127.0.0.1 --port 18090
# frontend (VITE_API_URL must match the backend port)
cd /tmp/opencode/uat/frontend && PORT=15190 VITE_API_URL=http://127.0.0.1:18090 npm run dev
```

Browser: Camofox REST at `http://127.0.0.1:9377` (`POST /start`, `POST /tabs/open`, `GET /tabs/{id}/snapshot`, `GET /tabs/{id}/screenshot`, `POST /tabs/{id}/evaluate`). All browser content was treated as untrusted data.

> Setup note: the frontend bakes `VITE_API_URL` at dev-server start; the backend's `FRONTEND_ORIGINS` must include the exact frontend origin or CORS preflight returns 400 "Disallowed CORS origin". Both are test-environment details, not product defects.

## 2. Passed tests

### 2.1 Authenticated API endpoints (46 passed)
Harness: `docs/uat-evidence/api-results.json`. Admin session login (200), then 46 read-only endpoints returned 2xx. Notable exact results:

| Endpoint | Observed |
| --- | --- |
| `/api/health` | `mode=research-only`, `paper_trading=true`, `broker_execution=false`, `registered_agents=550` |
| `/api/ready` | database ready/writable, `market_bars_schema=true`, storage ok |
| `/api/workers` | `count=550`, list length 550 (58.6 ms) |
| `/api/analytical-agents/runtime` | `agent_count=550`, 20 departments |
| `/api/skills` | `count=325`, execution `paper_trading=false`, `broker_execution=false` |
| `/api/paper/status` | 550 portfolios, $275,000 virtual capital, `enabled=true`, `trading_loop_running=true`, `broker_execution=false` |
| `/api/paper/stats` | 550 registered/initialized portfolios, 0 trades on the fresh DB |
| `/api/paper/rankings` | 550 ranked entries, `broker_execution=false` |
| `/api/analytical-agent-supervisor/status` | `status=not_started`, `registered_agent_count=550`, `continuous_daemon=separate_supervisor_process_required` |
| `/api/intelligence-core` | `enabled=false`, `provider=none`, `status=disabled_or_not_configured` |
| `/api/providers/status` | `no_live_provider_configured`; only `synthetic-fixture` adapter |
| `/api/market-data/sample` | `status=synthetic`, `source=synthetic-fixture`, 3 bars, explicit warning |
| `/api/market-data/overview` | `instrument_interval_count=0` (fresh DB) |
| `/api/workers/worker_001/memory` | `count=0` initially; `storage_mode=append_only_evidence_notes` |
| `/api/analytical-agents/worker_001/brain` | role-specific brain context returned |

Performance: 46 successful calls, min 1.6 ms, median 3.0 ms, p95 58.6 ms, max 443 ms (`/api/analytical-agents/learning-overview`, which aggregates 550 agents). No timeouts.

### 2.2 Error handling (expected non-2xx, correct behavior)
| Probe | Observed | Verdict |
| --- | --- | --- |
| Empty login credentials | 401 `Invalid credentials` | PASS |
| `limit=-1` on watchlist | 400 `limit must be between 1 and 500` | PASS |
| `GET /api/health` without auth where required | 401 on scoped endpoints | PASS (fail-closed) |
| 5xx / tracebacks in backend log | 0 / 0 | PASS |

### 2.3 Research workflow (`docs/uat-evidence/workflow.json`)
| Step | Observed |
| --- | --- |
| `POST /api/research/specialist-routing` | 200, 10 deterministic candidates, top `worker_001` |
| `POST /api/analytical-agents/worker_001/tasks/queue` | 202, task id `8e89da9e-...`, status `queued` |
| `GET /api/analytical-agents/worker_001/tasks` | 200, count 1 |
| `GET /api/analytical-agent-tasks/{id}` | 200, status `completed`, `execution_attempts=1` |
| `GET /api/analytical-agent-tasks/{id}/audit` | 200, 5 events: queued → dispatch_selected → claimed → completed → dispatch_finished |
| `POST /api/analytical-agent-supervisor/dispatch` | 200, `selected=1`, `dispatched=1`, `status=completed`, `dispatch_error_count=0` |
| `GET /api/agent-network/activity` | 200, `completed=1`, `latest_by_agent.worker_001.status=completed` |

### 2.4 Memory, skills, learning
| Test | Observed |
| --- | --- |
| `POST /api/workers/worker_001/memory` (`memory_type=observation`) | 200, memory id returned |
| `GET /api/workers/worker_001/memory` | 200, `count=2` after write |
| `POST /api/analytical-agents/worker_001/learning-feedback` | 200, `learning_effect=record_only_no_model_training` |
| `GET /api/analytical-agents/learning-overview` | 200, `total_feedback_records=1`, `agents_with_feedback=1` |
| `GET /api/workers/worker_001/improvement-proposals` | 200, `count=0` (no proposals on fresh DB; note states approval is not authorization to modify code/deploy/train) |

### 2.5 550-agent inventory consistency
All of the following independently reported **550**: `/api/workers` (list length 550), `/api/analytical-agents/runtime` (`agent_count`), `/api/health` (`registered_agents`), `/api/paper/status` (`registered_agents`, `initialized_portfolios`), `/api/paper/rankings` (550 rows), `/api/analytical-agent-supervisor/status` (`registered_agent_count`). Frontend banner also shows "550 WORKER PROFILES". No mismatch found. Note: the system is explicit that these are registered specialist profiles, not 550 autonomously running processes — `supervisor.status=not_started` and `continuous_daemon=separate_supervisor_process_required`.

### 2.6 Live research dashboard and browser modules
Frontend connected (`CONNECTED` banner), signed in as `admin · ADMIN`. All 20 sidebar modules were clicked in a real browser and screenshots captured under `docs/uat-evidence/`:

`overview`, `workflow`, `agent-network`, `agent-positions`, `learning-lab`, `agent-directory`, `runs`, `screener`, `coverage`, `news`, `research`, `data-validation`, `watchlist`, `portfolio`, `risk`, `system-health`, `providers`, `audit`, `backup`, `settings` (all `*.png` in `docs/uat-evidence/`; per-module click results in `module-results.json`).

Representative screenshots: `docs/uat-evidence/overview.png`, `docs/uat-evidence/agent-directory.png`, `docs/uat-evidence/research.png`, `docs/uat-evidence/system-health.png`.

## 3. Failed / degraded tests

### F-1 (P1) Authenticated endpoints return 401 from the main frontend app
**Observed:** after a successful sign-in, module views such as Agent Network, Runs, Coverage and Portfolio show "API activity unavailable", "0 / 550 profiles visible", "Valid user session required", or a stuck "LOADING…". Backend log shows repeated `401 Unauthorized` for `GET /api/workers?limit=550`, `/api/skills`, `/api/workspaces`, `/api/watchlist`, `/api/workflows/runs`, `/api/market-data/overview`, `/api/agent-network/activity`, `/api/analytical-agents/learning-overview`.
**Root cause (verified in browser):** `frontend/src/App.tsx` calls `fetch(API + '/api/...')` without `credentials: 'include'`. Controlled test on the same page with the same session:
- `fetch(.../api/workers?limit=550)` → **401**
- `fetch(..., {credentials:'include'})` → **200**
`AuthPanel.tsx` and `OperationsPanels.tsx` already use `credentials:'include'`; the main app does not.
**Impact:** cross-origin deployments (frontend origin ≠ API origin) show empty/degraded research modules. Same-origin deployments are unaffected (cookies are sent automatically).
**Recommended fix:** centralize all API calls in one client that always sets `credentials:'include'` (or add it to every `fetch` in `App.tsx`), then re-run this UAT. No backend change needed.

### F-2 (P2) Agent Network graph renders only the central core node
**Observed:** `docs/uat-evidence/agent-network.png` shows "550 registered profiles" in the header but "API activity unavailable – showing registered profiles only" and "0 / 550 profiles visible"; only the "MARKET-MIND-AI / shared intelligence core" node is drawn. This is partly caused by F-1 (the `/api/agent-network/activity` call 401s).
**Recommended fix:** fix F-1 first; if the graph still hides profiles when there is no task activity, render registered profiles as a "no activity yet" state instead of an empty canvas.

### F-3 (P2, environment limitation) No market data beyond a labelled synthetic fixture
**Observed:** `/api/providers/status` = `no_live_provider_configured`; `/api/market-data/overview` = 0 stored observations; `/api/market-data/sample` returns synthetic bars with an explicit warning. Paper trading loop is running but 0 trades were generated on the fresh DB because there are no stored bars for the configured symbols (the tick loop skips symbols with no bars).
**Recommended fix (operator action, not a code defect):** ingest licensed/stored OHLCV bars for configured symbols to exercise live paper signals; keep the synthetic fixture labelled as development-only.

### F-4 (P2, environment limitation) LLM-dependent features unavailable
**Observed:** `/api/intelligence-core` reports `enabled=false`, `provider=none`; task quality evaluation is `not_evaluated`; no model inference occurs. Research tasks still complete deterministically using supplied data and brain context.
**Recommended fix:** configure an external LLM provider (the repo has an existing OpenAI-compatible adapter) if qualitative synthesis is required; this does not require a local GPU.

## 4. Safety / constraints verified
- `/api/health` and `/api/paper/status` continuously reported `broker_execution=false`.
- No endpoint or UI action enabled real-money trading, wallet signing or autonomous live order execution.
- All paper activity is virtual ($500/agent, $275,000 total) and clearly labelled simulated.
- Verified baseline commit unchanged: `b47781aa3df633f9bc969221633e543d28ac877c` (`git rev-parse HEAD`).
- No merge, deploy, or file deletion; the three legacy files (`~/market_mind_app.js`, `~/market_mind_live_data.js`, `~/market_mind_terminal.html`) were not modified.

## 5. Known limitations
1. Testing used a fresh isolated database — most tables (memory, tasks, proposals, trades) start empty; results reflect a first-run state, not a mature deployment.
2. The frontend/backend were run on separate ports (cross-origin), which exposed F-1. A same-origin deployment may not show it, but the defect is real for documented cross-origin setups.
3. Camofox browser restarted several times during long sessions; each module test used a fresh tab with a consistent `userId`. All screenshots were captured successfully.
4. `jsdom`-based unit tests cannot evaluate CSS media queries; visual checks here use real browser screenshots.
5. The supervisor is a separate process; the API-triggered bounded dispatch was tested, not a continuously running daemon.
6. Response times are from localhost; no load or concurrency testing was performed.

## 6. Recommended next actions (priority order)
1. Fix F-1 by adding `credentials:'include'` to all frontend API fetches (single centralized client).
2. Re-run the 20-module browser pass and confirm Agent Network shows profiles and Portfolio/Runs/Watchlist no longer show 401-derived errors.
3. Ingest licensed/stored OHLCV bars for the configured paper-trading symbols; confirm virtual trades and P&L appear in the dashboard (provenance preserved, synthetic clearly labelled).
4. Optionally configure an external LLM provider for qualitative synthesis; re-test task quality evaluation.
5. Keep S3 restore, host recovery and independent review formally deferred as recorded in `FINAL_TEST_RESULTS.md`.

**Verdict: CONDITIONAL PASS.** All functional backend/research/paper-simulation paths tested behaved correctly; two UI defects (F-1 P1, F-2 P2) and two environment limitations (F-3, F-4) are documented with fixes. No real-money execution path was enabled or exercised.

---

# Phase 2 Remediation — completed 2026-11-25

**Baseline preserved:** `b47781aa3df633f9bc969221633e543d28ac877c` (unchanged, still in history).
**Remediation commit:** `f4ea61aa7cf24305c27d419ec7851a07a525541e`
`fix(ui): send session credentials on authenticated API requests` (pushed to
`feature/alpine-backend-runtime`; no merge, no deploy).

## R1 — P1 fixed: session credentials on authenticated requests

**Changes (7 files):** `frontend/src/apiClient.ts` gained `apiFetch()`, which opts
into `credentials:'include'` only for same-origin or `VITE_API_URL`-origin
requests — never arbitrary external URLs — and preserves an explicit caller
setting. All fetches in `App.tsx` (34), `AgentNetwork.tsx`, `AuthPanel.tsx`,
`LearningLab.tsx` and `OperationsPanels.tsx` now use `apiFetch`.
**Test first (TDD):** 4 new regression tests in `tests/ui/api-client.test.ts`
failed with `apiFetch is not a function` before the fix, passed after.

| Check | Result |
| --- | --- |
| `api-client.test.ts` | **8/8 PASS** (4 new + 4 existing) |
| Full UI suite | **131/131 PASS**, 21 files (was 127) |
| `npm test` | 10/10 PASS |
| App typecheck / test typecheck | PASS |
| Production build | PASS |
| npm audit | 0 vulnerabilities |
| Backend full suite (regression) | **1331 run, 0 failures, 0 errors, 1 skip** |

## R2 — P2 fixed: agent-network graph now shows all 550 relationships

Real-browser verification after the fix (Camofox, authenticated admin session):
- Agent Network: **550 / 550 profiles visible**, **1,290 VISUAL CONNECTIONS**,
  550 registered profiles, task activity endpoint returning 200 (no
  "API activity unavailable"). Evidence: `docs/uat-evidence/agent-network-after-fix.png`,
  `docs/uat-evidence/agent-network.png` (remediation pass).
- Overview: **CONNECTED**, **550 WORKER TEMPLATES**, Research Workers 550,
  Execution Mode DISABLED, no "Valid user session required" error. Evidence:
  `docs/uat-evidence/overview-after-fix.png`.
- Browser log proof: `/api/workers?limit=550` returned 200 after sign-in;
  controlled probe on the same page: raw `fetch(...)` = **401**,
  `fetch(...,{credentials:'include'})` = **200**.
- All 16 remaining 401s in the backend log occurred **before sign-in** (page
  mount-time fetches); after sign-in and reload every scoped endpoint returned
  200. This is expected fail-closed behavior, not a defect.

## R3 — Live market-data investigation (limitation confirmed, no code fix)

`/api/providers/status` is an explicit, honest static disclosure:
`status=no_live_provider_configured`, `live_providers=[]`, one adapter
`synthetic-fixture` (`data_status=synthetic`, "development and integration
testing only"). There is no licensed live/delayed data provider configured or
implemented in this checkout, and no provider credentials in the environment.
`/api/market-data/sample` returns 3 synthetic bars with the warning "Synthetic
development fixture only; not live, delayed, or historical market data."
`/api/market-data/overview` shows 0 stored observations on the fresh UAT DB.
With no stored bars, the paper loop skips symbols and generates no trades.
**No code change can invent live market data**; ingesting licensed OHLCV via
the existing import path is an operator action. Documented as limitation F-3.

## R4 — LLM core investigation (capability present, operator config required)

`/api/intelligence-core` reports `enabled=false`, `provider=none`,
`status=disabled_or_not_configured`. `intelligence_core_status()` selects
Mercury / FreeLLMAPI / Ollama from `INTELLIGENCE_CORE_*` env vars; none are
configured in this environment, and no API key is available (secrets must
never be fabricated or committed). The research capability itself is intact:
the deterministic workflow (routing → queue → dispatch → complete → audit)
passed in UAT, and `backend/tests/test_intelligence_core.py` has **14 passing
tests** including fake-provider synthesis and a safe fallback when no provider
is configured (`status=not_configured`, deterministic report authoritative).
`POST /api/intelligence-core/synthesize` without a provider explicitly reports
its fallback rather than inventing output. Qualitative LLM synthesis is an
operator-configured enhancement (see `docs/FREELLMAPI-INTEGRATION.md`); it is
not required for the research workflow to function. Documented as F-4.

## R5 — Full regression evidence

| Test | Baseline | After fix |
| --- | --- | --- |
| Authenticated API checks (46 + 2 error probes) | 46 2xx / 0 unexpected | **46 2xx / 0 unexpected** (`docs/uat-evidence/api-results-after-fix.json`) |
| Browser modules | 20/20 opened (degraded content) | **20/20 opened, content restored** (22 screenshots in `docs/uat-evidence/`) |
| Agent network profiles | 0 / 550 visible | **550 / 550 visible, 1,290 connections** |
| UI tests | 127 | **131** (4 new credential tests) |
| Backend tests | 1327 | **1331**, 0 failures/errors |
| 5xx / tracebacks | 0 / 0 | **0 / 0** |

No new defects were introduced by the remediation.

## Remaining defects / limitations (unchanged scope)
- **F-3 (operator, not code):** no licensed live market-data provider; synthetic
  fixture only. Operator must configure/import data to exercise live signals.
- **F-4 (operator, not code):** no LLM provider configured; deterministic
  research works, optional synthesis needs an operator-owned API key.
- **Accepted behavior:** authenticated endpoints return 401 before sign-in
  (fail-closed); the UI loads data after sign-in/reload. A usability improvement
  would be to refetch scoped data immediately on login instead of only on mount.
- S3 restore, host recovery and independent review remain formally deferred as
  recorded in `FINAL_TEST_RESULTS.md`.

**Concurrency note:** after this remediation was pushed, a separate local-only
commit `126e9444` ("fix(paper-trading): credit sale proceeds, price exits, mark
whole symbol", author `Market Mind Agent`) appeared on the branch tip. It is
**not pushed** — `origin/feature/alpine-backend-runtime` remains at `f4ea61aa` —
so it does not affect the CI evidence or this audit. It was not created by this
remediation and was left untouched.

**CI on remediation commit `f4ea61aa`: 9/9 check runs green** (Backend, Frontend,
Docker Compose integration, Trivy filesystem, container image scan, dependency
audit, real-browser tests, Vercel preview = `success`; cubic AI reviewer =
`neutral`, non-gating). Authoritative check runs:
`gh api repos/djny45/-MARKET-MIND-AI/commits/f4ea61aa/check-runs`.

**Final Phase 2 verdict: PASS for all in-scope code defects (F-1, F-2 fixed and
verified); F-3/F-4 are operator-environment limitations, not software failures.
No real-money trading, wallet signing, merge or deployment was performed.**
