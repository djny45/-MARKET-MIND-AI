# Deployment status — terminal database initialization fix

## Root cause

`src/app/page.tsx` called `getSnapshot()`, which throws when `DATABASE_URL`
is absent. The route caught the error and rendered `BootFallback`, so the
Vercel deployment showed only "awaiting database handshake". Every data API
(`/api/market`, `/api/agents`, `/api/signals`, `/api/scan`) returned HTTP 500.
The app itself built correctly; the missing DB was not configured in the
Vercel project environment.

## Fix (commit `63f51297`, branch `feature/motion-ai-3d-terminal`)

- Deterministic read-only synthetic demo adapter (`src/lib/demoSnapshot.ts`)
  reuses the existing 550-agent generator and instrument definitions.
- `src/lib/snapshot.ts` tries the DB-backed engine and falls back to the
  labelled demo snapshot. Homepage now always renders the full terminal.
- Every snapshot/API payload carries an explicit
  `dataOrigin: "database-simulated" | "demo-synthetic"`.
- An amber banner and footer explicitly state "read-only demo mode · database
  unavailable · synthetic sample data · not live market data".
- `/api/health` reports `database: "unconfigured"`, `demoMode: true`, a
  remediation hint, and HTTP 503 — it never claims connectivity and exposes
  no secrets.
- All data APIs degrade to labelled synthetic responses; `/api/scan` stays
  read-only in demo mode. No writes, brokers, real-money paths or migrations.

## Verification (executed locally)

| Check | Result |
|---|---|
| `npm run build` | pass |
| `npm run typecheck` | pass |
| `npm run lint` | pass |
| `node scripts/verify-terminal.mjs` (DB absent) | **24/24 checks pass** |
| Demo homepage | HTTP 200, full terminal, demo banner present |
| `/api/health` | HTTP 503, `demoMode: true`, honest diagnostic |
| `/api/market` | HTTP 200, `dataOrigin: demo-synthetic`, 12 instruments, 550 agents, 16 signals |

## Deployment

- Live URL checked: <https://motion-ai-3d-terminal.vercel.app>
- At verification time the live site still served the **old** build:
  `/api/market` returned no `dataOrigin`, and `/` still showed
  "awaiting database handshake". The GitHub PR head is `63f51297` and the
  Vercel check for the terminal still references the earlier deployment
  `BRdLgn5Xe7pLTk1CsE8wBxxdnvTH`, so the new commit has not been promoted yet.
- No manual Vercel deploy was triggered: no Vercel API token is available in
  this environment, and the task requires respecting deployment quota and
  approval. Do not repeatedly trigger failing workflows.

## Maintainer actions

1. Let the Vercel Git integration deploy PR #115 head `63f51297` (or approve
   the pending deployment in the Vercel dashboard). Quota/approval required.
2. Verify <https://motion-ai-3d-terminal.vercel.app/> shows the demo banner
   and `/api/market` returns `dataOrigin: "demo-synthetic"`.
3. Optional: provision `DATABASE_URL` and apply the committed Drizzle
   migration for persistent simulation. This is a production DB action and
   was NOT run here.

## Unrelated blocker observed

Backend pytest collection needs `fastapi` and other deps not installed in the
current environment (`ModuleNotFoundError: fastapi`). This is pre-existing
and unrelated to the frontend fix; no new dependencies were installed.
