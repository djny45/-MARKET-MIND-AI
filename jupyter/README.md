# JupyterLab private dashboard launcher — MARKET-MIND-AI

This directory contains the in-repository integration that makes the private
MARKET-MIND-AI dashboard available from an authenticated JupyterLab session.

## Files
- `market_mind_live.template.html` — dashboard template. `"__MM_SNAPSHOT__"` is
  replaced with a backend snapshot by the bridge (no secrets are embedded) and
  `__MM_VERSION__` with a per-snapshot cache token.
- `market_mind_dashboard.js` — the renderer. Published next to the page so the
  proxy route can load it over HTTP. The publisher also injects one copy inline
  for the Jupyter sandbox route; see the table below.
- `launcher.ipynb` — JupyterLab notebook with one clickable link that opens the
  dashboard from the Jupyter origin (sends a Referer → passes XSRF checks).

## Why the page ships two renderers

The snapshot is a `<script type="application/json">` data block (unaffected by
`script-src`), but the two routes accept different script forms. This was
verified in a real browser (Camofox) on 2026-11-25:

| Route | Policy | Renderer that works |
| --- | --- | --- |
| `/user/<name>/files/...` | `sandbox allow-scripts` (opaque origin) | **inline only** — same-URL external script is refused |
| `/user/<name>/proxy/8080/...` | proxy CSP `script-src 'self'` | **external only** — inline is refused |
| `/market_mind_live.html` (`:8080`) | same proxy CSP | **external only** |

`publish()` injects the inline copy from `market_mind_dashboard.js`, so keeping
the template free of inline JS is essential: the publisher can then add exactly
one copy at render time. Never paste the renderer into the template — that is
the regression this directory's tests guard against. Deleting either renderer
blank one of the routes.

## Why a launcher is required
Jupyter Server protects `GET /user/<name>/files/...` with XSRF/referer checks.
A URL opened directly in a mobile browser address bar has **no Referer** and is
rejected with `403 Blocking request from unknown origin`. Opening the dashboard
by clicking a link **inside JupyterLab** supplies a same-origin Referer, so the
request is authenticated, XSRF-checked and accepted — no security check is
disabled. The exact Jupyter origin is declared in the supported config:
`allow_origin` in `jupyter_server_config.d/01-market-mind-origin.json`.

A fresh browser with no Jupyter session cookie also needs `?token=...` on both
the page **and** the external script URL. This is why the launcher link is the
supported entry point: inside JupyterLab the session cookie authenticates both
requests. When testing with a token URL in a clean browser profile, the script
will 404 unless its URL carries the token too.

## Data flow
`scripts/jupyter_dashboard_bridge.py` logs into the local backend with the
existing 0600 operator credential file, reads `/api/paper/*`, per-symbol
`/api/market-data/history` and market overview over loopback, and writes a
snapshot HTML into Jupyter's served root and the frontend dist directory. No
tokens are printed or stored in the HTML.

## Open the dashboard
In JupyterLab, open `launcher.ipynb` from the file browser and click the link
in the first cell. Access stays inside `/user/<name>/` — private, no public
ingress, `broker_execution=false`.

## Verification (recorded 2026-11-25, commit `ea3ad00e`)

Run from the repository root. These are the exact commands and results used to
validate the dashboard and its delivery routes.

```bash
# 1. Dashboard bridge tests (no network, no credentials)
cd backend && python -m unittest tests.test_jupyter_dashboard_bridge -v

# 2. Full backend suite (the CI command in .github/workflows/quality.yml)
PYTHONPATH=backend python - <<'PY'
import unittest
suite = unittest.defaultTestLoader.discover("backend/tests")
print("discovered:", suite.countTestCases())
result = unittest.TextTestRunner(verbosity=1).run(suite)
print("run:", result.testsRun, "failures:", len(result.failures),
      "errors:", len(result.errors), "skipped:", len(result.skipped))
PY

# 3. Frontend unit, UI and typecheck
cd frontend && npm test && npm run test:ui && npm run typecheck:test

# 4. Production build (the bridge republishes the dashboard within 20s)
npm run build && sleep 25
curl -s -o /dev/null -w 'html=%{http_code}\n' http://127.0.0.1:8080/market_mind_live.html
curl -s -o /dev/null -w 'js=%{http_code}\n' http://127.0.0.1:8080/market_mind_dashboard.js

# 5. Audit
cd frontend && npm audit --audit-level=moderate
pip-audit -r backend/requirements.txt --format json

# 6. Health
python health_check.py     # from ~/.market-mind-ops
```

Results:

| Check | Command | Result |
| --- | --- | --- |
| Dashboard bridge tests | step 1 | **9/9 pass** |
| Backend suite | step 2 | **1318 run: 1317 pass, 0 fail, 0 errors, 1 skip** |
| Frontend node tests | `npm test` | **10/10 pass** |
| Frontend UI tests | `npm run test:ui` | **127/127 pass** (21 files) |
| Frontend typecheck | `npm run typecheck:test` | **pass** |
| Production build | `npm run build` | **pass** |
| Dashboard served after build | step 4 | **200** for both HTML and JS |
| npm audit | step 5 | **0 vulnerabilities** |
| pip-audit | step 5 | **No known vulnerabilities found** (39 requirements) |
| Health checks | step 6 | **20/20 pass** |
| All three routes (real browser) | Camofox | **live data on all three** — 6 KPIs, 4 priced symbols, 80 positions, 40 orders |

The production build deletes the published dashboard from `frontend/dist`; the
bridge restores it on its next 20-second cycle. A `404` immediately after a
build is expected — wait one cycle before re-testing.

The real-browser route checks used the Camofox REST server at `127.0.0.1:9377`
(`POST /start`, `POST /tabs/open`, `POST /tabs/{id}/evaluate`). Each route
reported `backend snapshot <UTC>Z`, 6 KPI tiles, 4 market rows with Binance
provenance, 80 open positions and 40 virtual orders. `broker_execution=false`
and `paper_trading=true` were preserved throughout.
