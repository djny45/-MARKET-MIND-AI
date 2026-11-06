"""Export offline historical indicator annotations to a browser-readable JSON file.

Run from repository root:
    python backend/examples/offline_indicator_report.py data.csv --ta-lib --output indicators.json
    python backend/examples/offline_indicator_report.py data.csv --ta-lib --timestamp-column timestamp --output indicators.json

This is retrospective research output only. It is not a forecast, trading signal,
recommendation, or execution system.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.offline_research_pipeline import run_offline_research


def _json_value(value: Any) -> Any:
    """Convert numpy/pandas scalar values to JSON-safe primitives."""
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def build_report(csv_path: str | Path, *, timestamp_column: str | None = None,
                 include_ta_lib: bool = False) -> dict[str, Any]:
    result = run_offline_research(
        csv_path, timestamp_column=timestamp_column, include_ta_lib=include_ta_lib
    )
    report: dict[str, Any] = {
        "report_type": "offline_historical_indicator_annotations",
        "status": "ok",
        "file": Path(csv_path).name,
        "row_count": int(result["row_count"]),
        "columns": list(result["columns"]),
        "timestamp_column": timestamp_column,
        "indicator_source": "TA-Lib" if include_ta_lib else "none",
        "indicators": {},
        "limitations": [
            "Historical annotations only; not forecasts or trade signals.",
            "Initial indicator lookback rows may be null.",
            "Validate chronological ordering and point-in-time availability before evaluation.",
        ],
    }
    for name, values in result["indicators"].get("ta_lib", {}).items():
        series = [_json_value(v) for v in values]
        valid = [v for v in series if isinstance(v, (int, float)) and math.isfinite(v)]
        report["indicators"][name] = {
            "values": series,
            "valid_count": len(valid),
            "null_count": len(series) - len(valid),
            "latest_valid": valid[-1] if valid else None,
        }
    if timestamp_column and timestamp_column in result["dataset"].columns:
        report["timestamps"] = [
            _json_value(v.isoformat() if hasattr(v, "isoformat") else v)
            for v in result["dataset"][timestamp_column]
        ]
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Local historical OHLCV CSV")
    parser.add_argument("--timestamp-column", help="Optional timestamp column")
    parser.add_argument("--ta-lib", action="store_true", help="Calculate optional TA-Lib annotations")
    parser.add_argument("--output", type=Path, help="Write JSON report to this path")
    args = parser.parse_args()
    try:
        report = build_report(args.csv_path, timestamp_column=args.timestamp_column,
                              include_ta_lib=args.ta_lib)
    except (OSError, UnicodeError, ValueError, RuntimeError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        args.output.expanduser().write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    print("Offline historical annotations only; no forecasts or trading actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
