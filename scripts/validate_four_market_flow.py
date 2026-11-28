"""Confirm real adapter data flows through the public API for all four markets."""
import json
import os
import tempfile

os.environ["MARKET_MIND_DB"] = tempfile.mkdtemp() + "/flow.db"
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
rows = []
for group, symbol in [
    ("us", "AAPL"), ("india", "RELIANCE"), ("forex", "EURUSD"), ("crypto", "BTCUSD")
]:
    body = client.get(
        f"/api/terminal/four-market?markets={group}&symbols={group}:{symbol}&refresh=true"
    ).json()
    market = body["markets"][0]
    quote = market["quotes"][0]
    row = {
        "market_group": group,
        "symbol": symbol,
        "status": quote["status"],
        "status_label": quote["status_label"],
        "last": quote["last"],
        "source": quote["source"],
        "timestamp": quote["timestamp"],
        "retrieved_at": quote["retrieved_at"],
        "exchange_timezone": quote["exchange_timezone"],
        "timestamp_exchange_local": quote["timestamp_exchange_local"],
        "market_status": market["market_status"],
    }
    rows.append(row)
    print(
        f"{group:6} {symbol:9} {row['status']:12} last={row['last']} "
        f"tz={row['exchange_timezone']} local={row['timestamp_exchange_local']}"
    )

with open("/tmp/opencode/api-market-flow.json", "w", encoding="utf-8") as handle:
    json.dump(rows, handle, indent=2)
