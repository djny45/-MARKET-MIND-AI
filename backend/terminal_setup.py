"""Print an educational, user-defined setup geometry report in the terminal."""
import argparse
import json

from app.setup_report import build_setup_report


def main() -> None:
    parser = argparse.ArgumentParser(description="MARKET-MIND-AI educational R:R calculator")
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--direction", required=True, choices=("long", "short"))
    parser.add_argument("--entry", required=True, type=float)
    parser.add_argument("--stop", required=True, type=float)
    parser.add_argument("--target", required=True, type=float)
    args = parser.parse_args()
    try:
        report = build_setup_report(args.symbol, args.direction, args.entry, args.stop, args.target)
    except ValueError as exc:
        parser.error(str(exc))
    print("MARKET-MIND-AI | EDUCATIONAL SCENARIO | EXECUTION DISABLED")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
