"""Compare two saved MARKET-MIND historical research evidence JSON exports."""

import argparse
import json
import sys
from pathlib import Path

from app.research_export_compare import compare_research_exports


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare two compatible historical research evidence exports.")
    parser.add_argument("before", help="Earlier evidence JSON file")
    parser.add_argument("after", help="Later evidence JSON file")
    parser.add_argument("--report", help="Optional path for the comparison report JSON")
    parser.add_argument("--strict", action="store_true", help="Return 1 unless both exports are integrity-verified and schema-compatible")
    args = parser.parse_args(argv)
    before_path, after_path = Path(args.before), Path(args.after)
    report_path = Path(args.report) if args.report else None
    if report_path and report_path.resolve() in {before_path.resolve(), after_path.resolve()}:
        print(json.dumps({"error": "report_path_must_not_overwrite_input"}))
        return 2
    try:
        before = json.loads(before_path.read_text(encoding="utf-8"))
        after = json.loads(after_path.read_text(encoding="utf-8"))
        result = compare_research_exports(before, after)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        print(json.dumps({"error": "comparison_failed", "detail": str(exc)}))
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if report_path:
        try:
            report_path.write_text(rendered, encoding="utf-8")
        except OSError as exc:
            print(json.dumps({"error": "report_write_failed", "detail": str(exc)}))
            return 2
    print(rendered, end="")
    if args.strict and result["comparison_status"] != "integrity_verified":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
