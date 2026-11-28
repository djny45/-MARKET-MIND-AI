# MARKET-MIND-AI — Private Testing Handoff

Date: 2026-11-28. Scope: controlled private, local, research-only use.
Production promotion remains on **HOLD**.

## 1. Commit identity (important)

- **Full local HEAD SHA: `5546177f644083d6958f87f9aca1bd1c374c696d`**
  (documentation-only commit adding this handoff / acceptance report).
- **Pushed and CI-validated PR head: `9fdc0220ae0013a70a86d2b90c1d80f39377555c`**.
- CI evidence below applies to `9fdc0220`. The local commit `5546177f` is
  documentation-only (no source changes) and has **no CI run** (`total_count=0`).
  To make the pushed head authoritative, push `5546177f` and re-run CI.

## 2. Working-tree state (honest disclosure)

`git status --short` at handoff time:

```
 M docs/external-evidence/four-market-resilience.json
 M jupyter/launcher.ipynb
?? jupyter/-MARKET-MIND-AI/
```

The tree is **not clean**. These three items are pre-existing, unrelated local
changes that were preserved, not created by this testing work. They do not
affect the terminal tests. The test instructions in this handoff match the
source at `9fdc0220` / `5546177f` (only docs changed between them).

## 3. Setup and test commands

### Linux / macOS (verified on this environment)

```bash
cd /home/jovyan/-MARKET-MIND-AI

# Backend (Python 3.11.6; venv at .venvs/backend)
PYTHONPATH=.:./backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q

# Terminal (Node 22.23.5)
cd landing-pages/motion-ai-3d-terminal
npm ci
npm run typecheck
npm run lint
npx drizzle-kit check
npm audit --audit-level=moderate
npm run build
node node_modules/next/dist/bin/next start -p 3123 &
node scripts/verify-terminal.mjs
node scripts/verify-unreachable-db.mjs
```

### Windows (PowerShell; paths adjusted)

```powershell
cd C:\path\to\-MARKET-MIND-AI
$env:PYTHONPATH = ".;.\backend"
.\.venvs\backend\Scripts\python.exe -m unittest discover -s backend\tests -q

cd landing-pages\motion-ai-3d-terminal
npm ci
npm run typecheck
npm run lint
npx drizzle-kit check
npm audit --audit-level=moderate
npm run build
Start-Process node -ArgumentList "node_modules/next/dist/bin/next start -p 3123"
node scripts/verify-terminal.mjs
node scripts/verify-unreachable-db.mjs
```

Use Node **22+** (Vitest/Next 16 requirement) and Python **3.11+**.

### Optional live research bars (private only)

```bash
# Linux/macOS
MARKET_MIND_RESEARCH_DB=/path/to/market_mind.db npm run start

# Windows PowerShell
$env:MARKET_MIND_RESEARCH_DB = "C:\path\to\market_mind.db"
npm run start
```

This is a read-only bridge to operator-attested `binance-public` 15m research
bars. It is disabled by default and must never be enabled in a public deployment.

## 4. Local services and environment variables

Services defined in `/home/jovyan/.market-mind-ops/services.json`:
`backend`, `proxy`, `supervisor`, `backup_scheduler`, `jupyter_bridge`,
`market_feed`. They are not required for the standalone terminal; the terminal
runs fully with `npm start` alone.

Terminal environment (from `landing-pages/motion-ai-3d-terminal/.env.example`):

| Variable | Purpose | Private default |
| --- | --- | --- |
| `DATABASE_URL` | PostgreSQL connection | **unset** (intentional) |
| `MARKET_MIND_API_URL` | Optional read-only FastAPI base URL | unset (self-contained) |
| `MARKET_MIND_API_TOKEN` | Optional bearer token for that backend | unset |
| `MARKET_MIND_API_TIMEOUT_MS` | Backend probe timeout | 5000 ms |
| `MARKET_MIND_RESEARCH_DB` | Optional local research-bars SQLite path | unset |

Backend operator env (names only from `private.env`): `MARKET_MIND_DB`,
`MARKET_MIND_ATTESTED_DATA_SOURCES`, `FRONTEND_ORIGINS`, auth/session settings,
backup/DR and encryption settings. Never paste their values into chat or repo.

## 5. DATABASE_URL absence and unavailable features

`DATABASE_URL` is **not set** (checked in the environment and in `private.env`).
ADR-006 (`docs/ARCHITECTURE_DECISIONS.md`) requires this for the current
release. Consequences:

- `/api/health` returns HTTP 503, `database: "unconfigured"`, `demoMode: true`.
- All market/agent/signal/scan endpoints return HTTP 200 with
  `dataOrigin: "demo-synthetic"` — deterministic synthetic fixtures.
- Unavailable: PostgreSQL persistence, database-backed simulation state,
  database-backed agent/signal history, any application migration.
- The opt-in `MARKET_MIND_RESEARCH_DB` bridge can display attested research bars
  read-only; it is not database-backed application state and never claims
  live/execution-grade prices.
- Do not "fix" the demo banner by setting `DATABASE_URL`.

## 6. CI and test evidence

- CI on exact pushed head `9fdc0220ae0013a70a86d2b90c1d80f39377555c`:
  - https://github.com/djny45/-MARKET-MIND-AI/actions/runs/46146341020
  - https://github.com/djny45/-MARKET-MIND-AI/actions/runs/46146336842
  All required jobs SUCCESS: Backend, Frontend, Docker Compose integration,
  Dependency audit, Trivy filesystem, Container image scan, Real browser
  responsive tests, Optional Zulip notification.
- Local results at the same source state: backend **1546 tests OK, 1 skipped**;
  typecheck/lint/build/drizzle-check/npm-audit all exit 0;
  `verify-terminal.mjs` **46 PASS exit 0**;
  `verify-unreachable-db.mjs` **21 PASS exit 0**;
  `scripts/check_doc_links.py` 89 files resolve.
- Detailed criteria: `docs/PRIVATE-TESTING-ACCEPTANCE-95816bf9.md`.

## 7. Production HOLD

Unchanged. All six external gates are 0/6 (`public_ingress_enabled: false`),
there is no independent `APPROVED` review, no exact-head READY Vercel preview
(terminal project rate-limited), no browser inspection, and
`verify-deployed.mjs` has not been run against any authorized target. No merge,
deployment, production setting change or security-gate bypass is authorized.
