#!/usr/bin/env python3
"""Jupyter dashboard data bridge — reads the live MARKET-MIND-AI backend API.

Publishes an authenticated-origin dashboard snapshot for the private JupyterLab
launcher. This script runs loopback-only, uses a read-only operator session, and
never prints tokens, cookies or credentials.

Data sources (all from the running backend, never invented):
  GET /api/paper/status          -> agent/portfolio counts, capital
  GET /api/paper/portfolios      -> equity, positions, P&L
  GET /api/paper/trades          -> virtual orders
  GET /api/market-data/overview  -> market data availability only
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = os.getenv("MM_BACKEND_URL", "http://127.0.0.1:8080")
OPS = Path(os.getenv("MM_OPS_DIR", "/home/jovyan/.market-mind-ops"))
TEMPLATE = Path(os.getenv("MM_DASH_TEMPLATE", "/home/jovyan/-MARKET-MIND-AI/jupyter/market_mind_live.template.html"))
DASHBOARD_JS = TEMPLATE.with_name("market_mind_dashboard.js")
DASHBOARD_JS_NAME = "market_mind_dashboard.js"
PUBLISH_DIRS = [
    Path("/home/jovyan"),
    Path("/home/jovyan/-MARKET-MIND-AI/frontend/dist"),
]
PUBLISH = [
    Path(os.getenv("MM_DASH_OUT", "/home/jovyan/market_mind_live.html")),
    Path("/home/jovyan/-MARKET-MIND-AI/frontend/dist/market_mind_live.html"),
]
STATE = Path(os.getenv("MM_DASH_STATE", str(OPS / "jupyter_dashboard_state.json")))
INTERVAL = 20.0


def _creds() -> tuple[str, str]:
    path = OPS / "operator-credentials.txt"
    for line in path.read_text(encoding="utf-8").splitlines():
        if " / " in line:
            user, password = line.split(" / ", 1)
            if user.strip() == "admin":
                return user.strip(), password.strip()
    raise RuntimeError("admin operator credential not configured")


class Session:
    """Minimal authenticated client: session cookie + CSRF from login response."""

    def __init__(self) -> None:
        self.cookies: dict[str, str] = {}
        self.csrf: str | None = None

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(BASE + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/json")
        req.add_header("Origin", BASE)
        if self.cookies:
            req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in self.cookies.items()))
        if self.csrf:
            req.add_header("X-CSRF-Token", self.csrf)
        with urllib.request.urlopen(req, timeout=15) as resp:
            for raw in resp.headers.get_all("Set-Cookie") or []:
                pair = raw.split(";", 1)[0]
                if "=" in pair:
                    k, v = pair.split("=", 1)
                    self.cookies[k.strip()] = v.strip()
            return resp.status, json.loads(resp.read() or b"null")

    def login(self) -> None:
        user, password = _creds()
        _, payload = self.request("POST", "/api/auth/login",
                                  {"username": user, "password": password})
        self.csrf = (payload or {}).get("csrf_token")
        if not self.csrf:
            raise RuntimeError("login did not issue a CSRF token")

    def logout(self) -> None:
        try:
            self.request("POST", "/api/auth/logout", {}, )
        except Exception:
            pass


def build_snapshot(client: Session) -> dict:
    _, status = client.request("GET", "/api/paper/status")
    _, portfolios = client.request("GET", "/api/paper/portfolios")
    market = []
    for symbol in ("BTCUSD", "ETHUSD", "SOLUSD", "BNBUSD"):
        try:
            _, data = client.request(
                "GET", f"/api/market-data/history?symbol={symbol}&interval=15m&limit=1")
            for bar in (data or {}).get("bars", [])[:1]:
                market.append({**bar, "symbol": symbol})
        except Exception:
            continue
    snap = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "market-mind-backend-api",
        "mode": "research-only",
        "broker_execution": False,
        "paper_trading": True,
        "market_data_note": "STORED observations only; no licensed live feed configured.",
        "market_data_status": "unavailable",
        "paper_note": "SIMULATED virtual orders; $500/agent; no real money or broker orders.",
        "market_prices": [],
        "open_positions": [],
        "virtual_orders": [],
        "pnl": {},
    }
    ps = portfolios.get("portfolios", []) if isinstance(portfolios, dict) else []
    snap["pnl"] = {
        "registered_agents": status.get("registered_agents"),
        "active_agents_with_positions": status.get("agents_with_open_positions"),
        "total_virtual_capital": status.get("total_virtual_capital"),
        "total_portfolio_value": status.get("total_portfolio_value"),
        "virtual_trades": 0,
        "realized_pnl": round(sum(p.get("realized_pnl", 0) for p in ps), 2),
        "max_drawdown_pct": round(max([p.get("max_drawdown", 0) for p in ps] or [0]) * 100, 4),
    }
    snap["open_positions"] = [
        {"agent_id": p["agent_id"], **pos}
        for p in ps for pos in p.get("positions", [])
        if pos.get("quantity")
    ][:80]
    # Recent virtual orders: one bounded query per active agent.
    orders = []
    for p in ps[:12]:
        _, data = client.request("GET", f"/api/paper/trades?agent_id={p['agent_id']}&limit=4")
        for trade in (data or {}).get("trades", []):
            orders.append(trade)
    orders.sort(key=lambda t: t.get("executed_at", ""), reverse=True)
    snap["virtual_orders"] = orders[:40]
    snap["pnl"]["virtual_trades"] = len(orders)
    # Market prices are reported only from backend-stored exchange observations.
    if market:
        snap["market_data_status"] = "available"
        snap["market_prices"] = [
            {k: b.get(k) for k in ("symbol", "close", "source", "status", "timestamp")}
            for b in market
        ]
    return snap


def publish(snap: dict) -> None:
    """Render and publish the dashboard for both Jupyter and the loopback proxy.

    The snapshot is emitted as a JSON *data block*, not executable script: the
    private proxy serves this page with `script-src 'self'`, which refuses
    inline JavaScript. Keeping the data out of the script policy and the
    behaviour in an external file keeps one page working on every route.
    """
    template = TEMPLATE.read_text(encoding="utf-8")
    # `</` is escaped so a string in the payload can never close the data block.
    payload = json.dumps(snap, default=str).replace("</", "<\\/")
    generated = str(snap.get("generated_at") or "")
    version = "".join(ch for ch in generated if ch.isalnum()) or "0"
    html = template.replace('"__MM_SNAPSHOT__"', payload).replace("__MM_VERSION__", version)
    dashboard_js = DASHBOARD_JS.read_text(encoding="utf-8")
    # Jupyter's /files/ sandbox gives an opaque origin, so its CSP refuses the
    # external same-URL script; the loopback proxy blocks inline scripts. Ship
    # both renderers: inline for Jupyter, external for the proxy. Injecting here
    # prevents template drift from removing the inline copy.
    if "MARKET-MIND-AI private dashboard renderer" not in html:
        html = html.replace(
            "</body>", "<script>\n" + dashboard_js + "\n</script>\n</body>")
    for out in PUBLISH:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
    for folder in PUBLISH_DIRS:
        if folder.is_dir():
            (folder / DASHBOARD_JS_NAME).write_text(dashboard_js, encoding="utf-8")
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(snap, indent=2, default=str), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="publish one snapshot and exit")
    args = parser.parse_args()
    running = {"ok": True}

    def stop(*_):
        running["ok"] = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running["ok"]:
        client = Session()
        try:
            client.login()
            publish(build_snapshot(client))
        except Exception as exc:  # never crash the bridge or expose internals
            print(f"[mm-jupyter] snapshot failed: {type(exc).__name__}", file=sys.stderr)
        finally:
            client.logout()
        if args.once:
            break
        for _ in range(int(INTERVAL * 5)):
            if not running["ok"]:
                break
            time.sleep(0.2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
