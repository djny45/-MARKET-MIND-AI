#!/usr/bin/env python3
"""Ingest genuine live OHLCV bars from Binance public klines into the market store.

Only public exchange REST data is used — no scraping, no credentials, no broker
orders. Source is labelled `binance-public`; live status requires operator
attestation via MARKET_MIND_ATTESTED_DATA_SOURCES. Symbols are normalized to the
platform naming (BTCUSD, ETHUSD, SOLUSD, BNBUSD).
"""
from __future__ import annotations

import argparse
import json
import signal
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/home/jovyan/-MARKET-MIND-AI/backend")

from app.market_data import DataStatus, MarketDataBatch, OHLCVBar  # noqa: E402
from app.market_store import store_batch  # noqa: E402

SYMBOLS = {
    "BTCUSD": "BTCUSDT",
    "ETHUSD": "ETHUSDT",
    "SOLUSD": "SOLUSDT",
    "BNBUSDT": "BNBUSDT",
}
SOURCE = "binance-public"
INTERVAL = "15m"
LIMIT = 120
SLEEP = 60.0


def fetch(symbol: str) -> list[OHLCVBar]:
    url = (
        "https://api.binance.com/api/v3/klines"
        f"?symbol={symbol}&interval={INTERVAL}&limit={LIMIT}"
    )
    with urllib.request.urlopen(url, timeout=15) as resp:
        rows = json.loads(resp.read())
    bars = []
    for row in rows:
        ts = datetime.fromtimestamp(row[0] / 1000, tz=timezone.utc)
        bars.append(OHLCVBar(
            timestamp=ts,
            open=float(row[1]), high=float(row[2]), low=float(row[3]),
            close=float(row[4]), volume=float(row[5]),
        ))
    return bars


def ingest(once: bool = False) -> int:
    running = {"ok": True}

    def stop(*_):
        running["ok"] = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    fetched = 0
    while running["ok"]:
        for platform_symbol, exchange_symbol in SYMBOLS.items():
            name = "BNBUSD" if platform_symbol == "BNBUSDT" else platform_symbol
            try:
                bars = fetch(exchange_symbol)
                batch = MarketDataBatch(
                    symbol=name, interval=INTERVAL, status=DataStatus.LIVE,
                    source=SOURCE, retrieved_at=datetime.now(timezone.utc),
                    bars=bars,
                    warnings=["Binance public klines; no licensed redistribution"],
                )
                result = store_batch(batch)
                fetched += result.get("stored", len(bars))
                print(f"[mm-feed] {name}: {len(bars)} bars", flush=True)
            except Exception as exc:
                print(f"[mm-feed] {name} failed: {type(exc).__name__}", file=sys.stderr, flush=True)
        if once:
            break
        for _ in range(int(SLEEP)):
            if not running["ok"]:
                break
            time.sleep(1)
    return fetched


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    raise SystemExit(0 if ingest(args.once) >= 0 else 1)
