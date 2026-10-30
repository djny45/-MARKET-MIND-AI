"""Print a descriptive report for bars already stored in the local SQLite database."""
import argparse
import json

from app.market_store import get_bars
from app.chart_research import build_chart_report


def main() -> None:
    parser = argparse.ArgumentParser(description="MARKET-MIND-AI stored-chart research report")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    history = get_bars(args.symbol, args.interval, args.limit)
    try:
        report = build_chart_report(history)
    except ValueError as exc:
        parser.error(str(exc))
    print("MARKET-MIND-AI | DESCRIPTIVE CHART RESEARCH | EXECUTION DISABLED")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
