"""Run a reproducible historical forecasting experiment on Yahoo daily bars.

Example (research only):
    python run_historical_research.py --symbol AAPL --bars 750

This script never places orders or emits trading signals.
"""
import argparse
import asyncio
import hashlib
import json
from datetime import timezone

from app.historical_forecasting import evaluate_next_day_return_forecast
from app.yahoo_finance_adapter import YahooFinanceAdapter


def _dataset_fingerprint(batch) -> str:
    """Hash the normalized source bars so a report can identify its exact input."""
    rows = []
    for bar in batch.bars:
        rows.append({
            "timestamp": bar.timestamp.astimezone(timezone.utc).isoformat(),
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "adjusted_close": bar.adjusted_close,
            "volume": bar.volume,
        })
    canonical = json.dumps(rows, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def run(symbol: str, bars: int) -> dict:
    batch = await YahooFinanceAdapter().get_bars(symbol, "1d", bars)
    closes = [
        bar.adjusted_close if bar.adjusted_close is not None else bar.close
        for bar in batch.bars
    ]
    report = evaluate_next_day_return_forecast(closes)

    # Forecast target return index j corresponds to the close timestamp j + 1.
    lookback = report["lookback"]
    train_end = report["split"]["train_samples"]
    validation_end = train_end + report["split"]["validation_samples"]
    target_dates = [bar.timestamp.astimezone(timezone.utc).isoformat()
                    for bar in batch.bars[lookback + 1:]]
    report["data"] = {
        "symbol": batch.symbol,
        "source": batch.source,
        "interval": batch.interval,
        "status": batch.status.value,
        "retrieved_at": batch.retrieved_at.astimezone(timezone.utc).isoformat(),
        "first_bar": batch.bars[0].timestamp.astimezone(timezone.utc).isoformat(),
        "last_bar": batch.bars[-1].timestamp.astimezone(timezone.utc).isoformat(),
        "bar_count": len(batch.bars),
        "price_field": "adjusted_close_when_available_else_close",
        "dataset_sha256": _dataset_fingerprint(batch),
        "warnings": batch.warnings,
    }
    report["evaluation_periods"] = {
        "train_target_start": target_dates[0],
        "train_target_end": target_dates[train_end - 1],
        "validation_target_start": target_dates[train_end],
        "validation_target_end": target_dates[validation_end - 1],
        "test_target_start": target_dates[validation_end],
        "test_target_end": target_dates[-1],
    }
    report["reproducibility"] = {
        "dataset_hash_algorithm": "SHA-256",
        "hash_scope": "all normalized returned OHLCV bars including adjusted_close",
        "note": "The hash identifies this fetched dataset snapshot; provider data may change on later retrieval.",
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", required=True, help="Yahoo Finance ticker, e.g. AAPL or RELIANCE.NS")
    parser.add_argument("--bars", type=int, default=750, help="Daily bars to request (30–5000)")
    args = parser.parse_args()
    result = asyncio.run(run(args.symbol, args.bars))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
