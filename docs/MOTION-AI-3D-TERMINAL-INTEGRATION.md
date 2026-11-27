# Motion AI 3D Terminal — integration evidence

Date: 2026-11-26 · Source: LimeWire share `hnkeT` (`motion-ai-3d-terminal (1).zip`)
Branch: `feature/motion-ai-3d-terminal` · Base: `e5e06623` (preserves both
security fixes: deny-by-default role gate and dev/build bundle isolation).

## ZIP verification

| Check | Result |
| --- | --- |
| Archive integrity (`unzip -t`) | `No errors detected in compressed data` |
| Entries | **79** (60 files + 19 directories) — matches the stated count |
| Uncompressed size | **551,282 bytes** (~551 KB) — matches |
| Shader HTML source documents | **18** — all present |
| All 35 explicitly named files | present |
| SHA-256 of downloaded ZIP | `eb0eec0554fab1e82128a38e15fb000e208d46310ccd4d4e08e5647bcc23a6ae` |

## What was added

```text
landing-pages/motion-ai-3d-terminal/
  60 source files from the ZIP, verbatim except the documented changes below
  + .env.example
  + README.md
  + src/shaders/fonts/fragment-mono.woff2  (OFL latin subset; ZIP omitted it)
  + src/lib/marketMindAdapter.ts           (optional read-only backend client)
  + src/app/api/backend/route.ts           (backend status probe)
```

## Documented deviations from the ZIP (all necessary)

1. **`src/db/index.ts`** — the original threw `DATABASE_URL is required` at
   module import. That broke `next build`, the homepage and `/api/health` on
   any machine without PostgreSQL. Replaced with a **lazy Drizzle/pg proxy**;
   same ORM and pool semantics, no throw at import.
2. **`src/app/api/health/route.ts`** — now returns `503` with
   `database: "unconfigured" | "unavailable"` instead of a bare `{ok:false}`
   with 500, so it never falsely claims a connection and distinguishes "not
   configured" from "configured but failing".
3. **`src/shaders/fonts/fragment-mono.woff2`** — `threeui.css:764` references
   this file; the ZIP's own README documents it as a required OFL asset that
   was not published in the archive. Build failed without it; downloaded the
   genuine Google Fonts latin subset (25,224 bytes, `wOF2` magic).
4. **Product identity** — user requested rename from "Aurum Synod Ω" to
   **MARKET MIND AI Ω** in `TerminalShell.tsx`, `layout.tsx`, `page.tsx`,
   `.env.example`. Internal engine identifiers and generated agent codenames,
   roles, models and instrument definitions are unchanged data.
5. **Demo-data disclosure** — footer now reads "simulated market data ·
   550 generated agent profiles · not verified performance".
6. **Optional backend adapter** — new typed read-only client using documented
   endpoints only (`/api/health`, `/api/workers`, `/api/terminal/providers`),
   disabled unless `MARKET_MIND_API_URL` is set.

## Actual commands and results

Run from `landing-pages/motion-ai-3d-terminal/`:

| Command | Result |
| --- | --- |
| `npm install` | **392 packages added**, 3 deprecation warnings (indirect), exit 0 |
| `npm run typecheck` (`tsc --noEmit`) | **PASS**, no output |
| `npm run lint` (`eslint .`) | **PASS**, no output |
| `npm run build` (`next build`) | **PASS**, exit 0, BUILD_ID `pjYakZmMf0hqVoDXjQgrC` |
| `npm audit --omit=dev` | **0 vulnerabilities** (production dependencies) |
| `npm audit` (incl. dev) | 4 moderate, all in dev-only `esbuild@0.18.20` nested under `drizzle-kit` via `@esbuild-kit/esm-loader` |

### Next.js security remediation (2026-11-27)

The initial import pinned `next` / `eslint-config-next` at **16.4.2**, which
Trivy flagged with **7 MEDIUM CVEs** (CVE-2026-119346/347/348/349/350/351 and
CVE-2026-119790 — cookie/header disclosure, SVG DoS, HTTP response
desynchronisation, cache-key and fallback-shell poisoning, and a cross-request
cache-dedup race). All are fixed in **16.4.5+**. Both packages were upgraded to
**16.4.6** and the lockfile regenerated with `npm install` (never hand-edited).
Post-upgrade: `npm audit --omit=dev` reports **0**; the remaining 4 moderate
findings are dev-only transitive `esbuild` copies that Trivy's lockfile scan
excludes by default (it suppresses development dependencies) and are not
shipped in the production bundle. Typecheck, lint and `next build` all pass on
16.4.6 (routes unchanged).

### Built routes

```text
ƒ /                    ƒ /api/backend       ƒ /api/market
ƒ /api/agents          ƒ /api/agents/[id]   ƒ /api/health
ƒ /api/scan            ƒ /api/signals       ○ /icon.svg
```

## Functional checks (actually executed)

`npm run start -- --hostname 127.0.0.1 --port 3000` was launched and probed
over real HTTP:

| Check | Status | Evidence |
| --- | --- | --- |
| `GET /` | **200**, 8,459 bytes | title `MARKET MIND AI · 550-Agent Research Terminal`, database-less fallback screen |
| `GET /api/health` | **503** | `{"ok":false,"database":"unconfigured","detail":"DATABASE_URL is not set"}` — honest |
| `GET /api/backend` | **200** | `{"status":"disabled","dataOrigin":"local-simulation"}` |
| `GET /api/market` | **500** | `{"error":"market_unavailable"}` — explicit, not fabricated |
| `GET /api/agents?perPage=2` | **500** | `{"error":"agents_unavailable"}` |
| `GET /api/signals?limit=5` | **500** | `{"error":"signals_unavailable"}` |
| `GET /api/agents/worker_001` | **400** | `{"error":"invalid_agent_id"}` |

Browser smoke test (real Chromium via Playwright, 3 viewports):

| Viewport | HTTP | Horizontal overflow | Console errors |
| --- | --- | --- | --- |
| Desktop 1280 | 200 | none | 0 |
| Tablet 810 | 200 | none | 0 |
| Mobile 412 | 200 | none | 0 |

Screenshot: `docs/external-evidence/screenshots/motion-ai-3d-terminal-fallback.png`
(+ `-evidence.json`).

## Checks that could NOT be executed (honest)

No PostgreSQL server or client binaries exist in this environment (port 5432
closed, no `psql`/`postgres`). An attempt to exercise the engine through an
in-memory `pg-mem` substitute failed because `pg-mem` does not implement the
`rowMode` option Drizzle uses; that harness was removed and no result from it
is claimed. Therefore:

- Market/agent/signal/scan endpoints returning **real seeded data** were not
  exercised. Only their explicit database-unavailable behaviour was verified.
- The full `TerminalShell` panel layout, market selection, watchlist selection,
  agent search/filter/sort/pagination, drawer, consensus board, signal feed and
  the 3D ConstellationField **could not be rendered** because `page.tsx`
  correctly shows the fallback screen without a database.
- Shader CDN loading and animation were not verified offline.
- The optional backend adapter was typechecked and built but not exercised
  against a live authenticated MARKET-MIND-AI backend.

These are the only unverified items; none is marked as passed.

## Protection of existing work

- Branch created **from `e5e06623`**, not from `main`: both security fixes and
  all 93 commits of four-market/Zulip/Tredye/daily-cycle work are preserved.
- No existing frontend/backend file, package file, agent registry, skill or
  database was modified. Only the root `README.md` gained a link.
- `jupyter/launcher.ipynb` remains the user's pre-existing uncommitted edit
  and was never staged.

## Next validation needed (external)

Provision PostgreSQL, set `DATABASE_URL`, run `npx drizzle-kit push`, restart,
then verify the seeded terminal UI and shader in a browser, and exercise all
API routes with data.
