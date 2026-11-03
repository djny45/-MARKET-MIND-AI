"""Run independent historical forecasting research across multiple symbols.

This is a research-only batch runner. It does not rank instruments, emit
trading signals, or place orders. Each symbol is evaluated independently.
"""
import argparse
import asyncio
import json
from datetime import datetime, timezone

from run_historical_research import run


async def run_batch(
    symbols: list[str],
    bars: int,
    *,
    walk_forward: bool = True,
    min_train_samples: int = 100,
    test_window_size: int = 20,
    step_size: int | None = None,
) -> dict:
    """Evaluate each symbol separately and preserve per-symbol failures."""
    normalized = []
    seen = set()
    for raw_symbol in symbols:
        symbol = raw_symbol.strip()
        if symbol and symbol.upper() not in seen:
            seen.add(symbol.upper())
            normalized.append(symbol)
    if not normalized:
        raise ValueError("provide at least one non-empty symbol")

    results = []
    for symbol in normalized:
        try:
            report = await run(
                symbol, bars, walk_forward=walk_forward,
                min_train_samples=min_train_samples,
                test_window_size=test_window_size,
                step_size=step_size,
            )
            results.append({
                "symbol": symbol,
                "status": "success",
                "dataset_sha256": report.get("data", {}).get("dataset_sha256"),
                "evaluation_mode": report.get("evaluation_mode"),
                "report": report,
            })
        except Exception as exc:
            # Keep failures explicit; do not synthesize missing metrics.
            results.append({
                "symbol": symbol,
                "status": "error",
                "error_type": type(exc).__name__,
                "error": str(exc),
            })

    successful = [item for item in results if item["status"] == "success"]
    failed = [item for item in results if item["status"] == "error"]
    return {
        "report_type": "independent_multi_symbol_historical_research",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "requested_symbols": normalized,
        "bars_requested_per_symbol": bars,
        "evaluation_mode": "expanding_walk_forward" if walk_forward else "single_chronological_holdout",
        "research_only": True,
        "summary": {
            "symbols_requested": len(normalized),
            "symbols_succeeded": len(successful),
            "symbols_failed": len(failed),
        },
        "results": results,
        "interpretation_notes": [
            "Each symbol has its own dataset, split, and evaluation; metrics are not pooled across symbols.",
            "This batch report does not rank symbols or imply investment suitability.",
            "Historical forecast errors do not establish profitability or future predictive edge.",
            "Provider snapshots may change; retain each dataset SHA-256 for reproducibility.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", required=True,
                        help="Comma-separated Yahoo tickers, e.g. AAPL,MSFT,RELIANCE.NS")
    parser.add_argument("--bars", type=int, default=750,
                        help="Daily bars requested per symbol (adapter-supported range)")
    parser.add_argument("--holdout", action="store_true",
                        help="Use single chronological holdout instead of walk-forward")
    parser.add_argument("--min-train-samples", type=int, default=100)
    parser.add_argument("--test-window-size", type=int, default=20)
    parser.add_argument("--step-size", type=int, default=None)
    args = parser.parse_args()
    result = asyncio.run(run_batch(
        args.symbols.split(","), args.bars,
        walk_forward=not args.holdout,
        min_train_samples=args.min_train_samples,
        test_window_size=args.test_window_size,
        step_size=args.step_size,
    ))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
