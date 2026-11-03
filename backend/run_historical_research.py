"""Run a reproducible historical forecasting experiment on Yahoo daily bars.

Example (research only):
    python run_historical_research.py --symbol AAPL --bars 750

This script never places orders or emits trading signals.
"""
import argparse
import asyncio
import json
from datetime import timezone

from app.historical_forecasting import evaluate_next_day_return_forecast
from app.yahoo_finance_adapter import YahooFinanceAdapter


async def run(symbol: str, bars: int) -> dict:
    batch = await YahooFinanceAdapter().get_bars(symbol, "1d", bars)
    closes = [
        bar.adjusted_close if bar.adjusted_close is not None else bar.close
        for bar in batch.bars
    ]
    report = evaluate_next_day_return_forecast(closes)
    report["data"] = {
        "symbol": batch.symbol,
        "source": batch.source,
        "interval": batch.interval,
        "status": batch.status.value,
        "retrieved_at": batch.retrieved_at.astimezone(timezone.utc).isoformat(),
        "first_bar": batch.bars[0].timestamp.isoformat(),
        "last_bar": batch.bars[-1].timestamp.isoformat(),
        "bar_count": len(batch.bars),
        "price_field": "adjusted_close_when_available_else_close",
        "warnings": batch.warnings,
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
