"""Print single- or multi-timeframe descriptive research from local stored bars."""
import argparse
import json

from app.market_store import get_bars
from app.chart_research import build_chart_report
from app.multi_timeframe import build_multi_timeframe_report, SUPPORTED_INTERVALS
from app.deep_analysis import build_deep_analysis_report


def main() -> None:
    parser = argparse.ArgumentParser(description="MARKET-MIND-AI chart research report")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--mode", choices=("single", "multi"), default="single")
    parser.add_argument("--interval", default="1d", choices=SUPPORTED_INTERVALS)
    parser.add_argument("--intervals", default="15m,1h,4h,1d")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--deep", action="store_true", help="include integrated data-quality and structure diagnostics")
    parser.add_argument("--correlate-symbols", default="", help="comma-separated symbols for timestamp-aligned historical correlation; requires --deep")
    args = parser.parse_args()
    if args.correlate_symbols and not args.deep:
        parser.error("--correlate-symbols requires --deep")

    try:
        if args.mode == "single":
            report = build_chart_report(get_bars(args.symbol, args.interval, args.limit))
            title = "SINGLE-TIMEFRAME"
        else:
            intervals = [item.strip() for item in args.intervals.split(",") if item.strip()]
            if not intervals or len(intervals) > 4 or any(item not in SUPPORTED_INTERVALS for item in intervals):
                parser.error("--intervals must be a comma-separated subset of 15m,1h,4h,1d")
            histories = {
                interval: get_bars(args.symbol, interval, args.limit)
                for interval in intervals
            }
            report = build_multi_timeframe_report(args.symbol, histories)
            title = "MULTI-TIMEFRAME"
    except ValueError as exc:
        parser.error(str(exc))

    if args.deep:
        histories = ({args.interval: get_bars(args.symbol, args.interval, args.limit)}
                     if args.mode == "single" else histories)
        correlation_histories = None
        if args.correlate_symbols:
            symbols = sorted({item.strip().upper() for item in args.correlate_symbols.split(",") if item.strip()} | {args.symbol.upper()})
            if len(symbols) > 12:
                parser.error("--correlate-symbols supports at most 12 total symbols including --symbol")
            correlation_histories = {name: get_bars(name, args.interval if args.mode == "single" else intervals[0], args.limit) for name in symbols}
        report = build_deep_analysis_report(args.symbol, histories,
                                            report if args.mode == "multi" else None,
                                            correlation_histories)
        title = "DEEP " + title

    print(f"MARKET-MIND-AI | {title} DESCRIPTIVE RESEARCH | EXECUTION DISABLED")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
