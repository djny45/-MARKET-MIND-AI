# JupyterLab private dashboard launcher — MARKET-MIND-AI

This directory contains the in-repository integration that makes the private
MARKET-MIND-AI dashboard available from an authenticated JupyterLab session.

## Files
- `market_mind_live.template.html` — dashboard template (`/*__MM_SNAPSHOT__*/`
  is replaced with a backend snapshot by the bridge; no secrets are embedded).
- `launcher.ipynb` — JupyterLab notebook with one clickable link that opens the
  dashboard from the Jupyter origin (sends a Referer → passes XSRF checks).

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
