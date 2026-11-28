#!/usr/bin/env python3
"""Collect historical 15-minute crypto, silver and crude-oil research bars.

This is a research-data collector, not a real-time quote feed or execution
service. Yahoo Finance chart observations remain HISTORICAL and retain their
provider/retrieval provenance in the existing market_bars store.
"""
from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.market_store import store_batch  # noqa: E402
from app.yahoo_finance_adapter import YahooFinanceAdapter  # noqa: E402

# Platform symbol -> Yahoo Finance chart symbol. Futures symbols are continuous
# research contracts; they are not the same as a specific dated futures expiry.
SYMBOLS = {
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "XAGUSD": "SI=F",
    "WTI": "CL=F",
    "BRENT": "BZ=F",
}
INTERVAL = "15m"
LIMIT = 120
DEFAULT_POLL_SECONDS = 900


async def ingest_once(adapter: YahooFinanceAdapter | None = None) -> dict[str, dict]:
    """Fetch and persist each asset independently; one provider failure won't stop the batch."""
    provider = adapter or YahooFinanceAdapter()
    results: dict[str, dict] = {}
    for platform_symbol, provider_symbol in SYMBOLS.items():
        try:
            batch = await provider.get_bars(provider_symbol, INTERVAL, LIMIT)
            # Store under the platform symbol used by terminal/history queries.
            # Keep the provider ticker in the explicit mapping and provider source
            # metadata; never rewrite the source or the HISTORICAL status.
            platform_batch = batch.model_copy(update={"symbol": platform_symbol})
            results[platform_symbol] = store_batch(platform_batch)
            print(
                f"[asset-research] {platform_symbol} <- {provider_symbol}: "
                f"{len(batch.bars)} {batch.interval} bars ({batch.status.value})",
                flush=True,
            )
        except Exception as exc:  # isolate provider outages per instrument
            results[platform_symbol] = {"status": "unavailable", "error": type(exc).__name__}
            print(
                f"[asset-research] {platform_symbol} unavailable: {type(exc).__name__}",
                file=sys.stderr,
                flush=True,
            )
    return results


async def run(poll_seconds: int, once: bool) -> int:
    if poll_seconds < 60:
        raise ValueError("poll interval must be at least 60 seconds")
    stopping = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stopping.set)
        except NotImplementedError:
            pass

    while not stopping.is_set():
        await ingest_once()
        if once:
            break
        try:
            await asyncio.wait_for(stopping.wait(), timeout=poll_seconds)
        except asyncio.TimeoutError:
            continue
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="collect one batch and exit")
    parser.add_argument(
        "--poll-seconds", type=int, default=DEFAULT_POLL_SECONDS,
        help="poll interval (minimum 60; default 900)",
    )
    args = parser.parse_args()
    return asyncio.run(run(args.poll_seconds, args.once))


if __name__ == "__main__":
    raise SystemExit(main())
