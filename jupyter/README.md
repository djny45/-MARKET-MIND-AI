# JupyterLab private dashboard launcher — MARKET-MIND-AI

This directory contains the in-repository integration that makes the private
MARKET-MIND-AI dashboard available from an authenticated JupyterLab session.

## Files
- `market_mind_live.template.html` — dashboard template. `"__MM_SNAPSHOT__"` is
  replaced with a backend snapshot by the bridge (no secrets are embedded) and
  `__MM_VERSION__` with a per-snapshot cache token.
- `market_mind_dashboard.js` — the renderer. Published next to the page so it
  loads over HTTP; holds all behaviour, so the page needs no inline script.
- `launcher.ipynb` — JupyterLab notebook with one clickable link that opens the
  dashboard from the Jupyter origin (sends a Referer → passes XSRF checks).

## Why the snapshot is a data block, not inline script
The page is served from two places with different policies:

| Route | Policy | Consequence |
| --- | --- | --- |
| `/user/<name>/files/...` | Jupyter sandbox | inline script allowed, no same-origin `fetch` |
| `/proxy/8080/...` | proxy CSP `script-src 'self'` | inline script **refused** |

The snapshot therefore ships as `<script type="application/json">` (a data
block, unaffected by `script-src`) and the renderer is an external same-origin
file, which both routes accept. This is why the dashboard must not be changed
back to an inline `<script>`: it would render blank behind the private proxy.

## Why a launcher is required
Jupyter Server protects `GET /user/<name>/files/...` with XSRF/referer checks.
A URL opened directly in a mobile browser address bar has **no Referer** and is
rejected with `403 Blocking request from unknown origin`. Opening the dashboard
by clicking a link **inside JupyterLab** supplies a same-origin Referer, so the
request is authenticated, XSRF-checked and accepted — no security check is
disabled. The exact Jupyter origin is declared in the supported config:
`allow_origin` in `jupyter_server_config.d/01-market-mind-origin.json`.

## Data flow
`scripts/jupyter_dashboard_bridge.py` logs into the local backend with the
existing 0600 operator credential file, reads `/api/paper/*` and
`/api/market-data/overview` over loopback, and writes a snapshot HTML into
Jupyter's served root. No tokens are printed or stored in the HTML.

## Open the dashboard
In JupyterLab, open `launcher.ipynb` from the file browser and click the link
in the first cell. Access stays inside `/user/<name>/` — private, no public
ingress, `broker_execution=false`.
