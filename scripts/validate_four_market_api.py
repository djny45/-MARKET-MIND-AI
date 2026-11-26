"""Exercise the real API routes with a temporary database (no live server auth)."""
import json
import os
import tempfile
import time

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/api-validation.db"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
results = {}


def check(name, path):
    started = time.time()
    response = client.get(path)
    elapsed = round(time.time() - started, 3)
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}
    if response.status_code == 200:
        if "instruments" in body:
            summary = f"{len(body['instruments'])}: {[i.get('symbol') for i in body['instruments'][:3]]}"
        elif "symbols" in body:
            summary = f"watchlist={body['symbols']}"
        elif "markets" in body and "totals" in body:
            summary = f"markets={[m['market_group'] for m in body['markets']]} totals={body['totals']}"
        elif "markets" in body:
            summary = f"summary={len(body['markets'])} rows"
        elif "providers" in body:
            summary = f"adapters={[p['name'] for p in body['providers']['adapters']]}"
        elif "available_adapters" in body:
            summary = f"adapters={[a['name'] for a in body['available_adapters']]}"
        elif "bars" in body:
            summary = f"bars={len(body['bars'])} status={body.get('status')}"
        else:
            summary = str(body)[:100]
    else:
        summary = str(body)[:150]
    print(f"{name:26} HTTP={response.status_code} {elapsed}s  {summary}")
    results[name] = {"path": path, "status": response.status_code, "elapsed": elapsed, "summary": summary}


check("instrument search US", "/api/instruments?q=AAPL&market_group=us&limit=5")
check("instrument search India", "/api/instruments?q=RELIANCE&market_group=india&limit=5")
check("instrument search forex", "/api/instruments?q=EURUSD&market_group=forex&limit=5")
check("instrument search crypto", "/api/instruments?q=BTC&market_group=crypto&limit=5")
check("instrument master all", "/api/instrument-master?limit=10")
check("watchlist", "/api/watchlist")
check("chart history", "/api/market-data/history?symbol=AAPL&interval=1d&limit=3")
check("terminal filtered board", "/api/terminal/four-market?markets=us&symbols=us:AAPL&refresh=true")
check("terminal summary", "/api/terminal/four-market/summary")
check("terminal providers", "/api/terminal/providers")
check("providers status", "/api/providers/status")

with open("/tmp/opencode/api-validation.json", "w", encoding="utf-8") as handle:
    json.dump(results, handle, indent=2)
