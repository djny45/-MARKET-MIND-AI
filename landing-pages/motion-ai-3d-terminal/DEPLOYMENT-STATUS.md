# Deployment status — terminal database initialization fix

## Exact root cause

Two independent defects produced the stuck screen:

1. **Stale production deployment.** The live URL
   `https://motion-ai-3d-terminal.vercel.app` serves an **old build** whose
   `src/app/page.tsx` caught the missing-`DATABASE_URL` error and rendered
   `BootFallback` ("MARKET MIND CORE BOOTING" / "AWAITING DATABASE HANDSHAKE").
   Evidence as of 2026-11-28: `/` is 8.8 KB with the boot screen; `/api/market`
   returns HTTP 500 `market_unavailable`; `/api/health` returns the old payload
   without `demoMode`. The fixed code is committed at branch
   `feature/motion-ai-3d-terminal` but has not been promoted to production.
2. **Unbounded database wait (found and fixed in this pass).** With
   `DATABASE_URL` set but unreachable, `new Pool({ connectionString })`
   defaults to `connectionTimeoutMillis: 0` (infinite) and no query timeout.
   `Promise.race`-less `loadSnapshot()` blocked forever, so the fixed build
   would still have hung on a dead database. Reproduced locally against
   `203.0.113.1:5432`: requests did not settle even after 40 seconds.

The failed dependency is **PostgreSQL connectivity/configuration in the Vercel
project** (`DATABASE_URL` is unset on the deployed project) combined with the
old build's lack of a fallback. The app itself builds and runs.

## Fix

- Lazy Drizzle/`pg` proxy (existing adapter) with bounded
  `connectionTimeoutMillis`, `query_timeout`, `idleTimeoutMillis` and `max`.
- `withDatabaseTimeout()` hard deadline (`DATABASE_TIMEOUT_MS`, default 4000 ms)
  plus one bounded retry; demo fallback always wins after the deadline.
- Read-only schema probe (`information_schema.tables`) — no migrations, no
  writes, no production data modification. `/api/health` reports database
  readiness separately from agent-grid readiness (read-only agent count).
- `/api/health` and `/api/market` return fixed, non-sensitive diagnostics;
  detailed errors go to server logs only.
- Client demo labelling derives from each poll's `dataOrigin`, so refresh or
  recovery cannot leave a stale banner.
- Honest counts: "online" = active + scanning + debating profiles; total is
  labelled as generated profiles, not 550 autonomous agents.
- Agent routes log fallback reasons so real query defects are not masked.
- Expanded verification harnesses (see below).

## Verification (executed locally, 2026-11-28)

| Check | Result |
|---|---|
| `npm run build` (clean) | pass |
| `npm run typecheck` | pass |
| `npm run lint` | pass |
| `node scripts/verify-terminal.mjs` (DB absent) | **32/32 pass** |
| `node scripts/verify-unreachable-db.mjs` (black-holed DB) | **9/9 pass**, 3.0–3.2 s per request |
| Backend unavailable (`MARKET_MIND_API_URL` bogus) | `/api/backend` → `status: "unavailable"`, homepage still renders full terminal |
| Demo homepage | HTTP 200, ~229 KB, banner present, no boot screen |
| `/api/health` | HTTP 503, `database: unconfigured`, `demoMode: true`, no secrets |
| Live deployed `node scripts/verify-deployed.mjs` | **6 failures** — confirms production is stale |

Scenarios not executable here: a real empty PostgreSQL database and a real
database-backed agent service (no Postgres binaries or credentials in this
environment, and starting one would require provisioning). The code reports
these states read-only via `schema-incomplete` / `agents.ready: false`, and no
seeding or migration was run.

## Deployment (blocked — operator action required)

- Per operator decision, **no deploy was triggered** in this pass; the repo
  policy also states public deployment is not authorized without approval.
- No Vercel token/bypass exists in this environment; the Vercel preview check
  for the PR is protected by Vercel Authentication.
- Promote the verified commit of PR #115 (`feature/motion-ai-3d-terminal`) in
  the Vercel dashboard, then re-run:
  `node scripts/verify-deployed.mjs https://motion-ai-3d-terminal.vercel.app`
  Expected: boot fallback absent, demo banner present, `/api/market` 200 with
  `dataOrigin: demo-synthetic`.
- Keep `DATABASE_URL` unset unless a real PostgreSQL instance is provisioned.
  Applying the committed Drizzle migration remains a separate, approved DB
  action and was NOT performed.

## Documentation updated

`README.md` now documents the bounded timeout, honest health semantics and the
unreachable-DB regression script. `scripts/verify-deployed.mjs` no longer
hard-codes stale deployment IDs.
