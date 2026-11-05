"""Generate a compact JSON quality summary for a local OHLCV CSV.

Run from the repository root:
    python backend/examples/offline_dataset_report.py path/to/data.csv
    python backend/examples/offline_dataset_report.py path/to/data.csv --timestamp-column timestamp --output report.json

The report is historical dataset metadata only. It does not create forecasts,
trading signals, or execute external actions.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Support the documented repository-root invocation without requiring an
# editable install or an implicit PYTHONPATH=backend environment variable.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.offline_dataset import load_ohlcv_csv


def build_report(path: str | Path, *, timestamp_column: str | None = None) -> dict[str, Any]:
    """Validate a local OHLCV CSV and return descriptive statistics."""
    source = Path(path).expanduser()
    frame = load_ohlcv_csv(source, timestamp_column=timestamp_column)

    report: dict[str, Any] = {
        "status": "ok",
        "file": source.name,
        "file_size_bytes": source.stat().st_size,
        "row_count": int(len(frame)),
        "columns": list(frame.columns),
        "numeric_summary": {},
        "quality_checks": {
            "ohlc_validated": True,
            "finite_ohlc_values": True,
            "nonnegative_volume": "volume" not in frame.columns or bool((frame["volume"] >= 0).all()),
        },
    }

    for column in ("open", "high", "low", "close", "volume"):
        if column in frame.columns:
            values = frame[column]
            report["numeric_summary"][column] = {
                "min": float(values.min()),
                "max": float(values.max()),
                "mean": float(values.mean()),
            }

    if timestamp_column:
        normalized = timestamp_column.strip().lower()
        timestamps = frame[normalized]
        report["time_range_utc"] = {
            "start": timestamps.min().isoformat(),
            "end": timestamps.max().isoformat(),
        }
        report["quality_checks"]["unique_timestamps"] = True
        report["quality_checks"]["chronological_after_sort"] = bool(timestamps.is_monotonic_increasing)

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to a local OHLCV CSV")
    parser.add_argument("--timestamp-column", help="Optional timestamp column name")
    parser.add_argument("--output", type=Path, help="Optional path to save JSON report")
    args = parser.parse_args()

    try:
        report = build_report(args.csv_path, timestamp_column=args.timestamp_column)
    except (OSError, UnicodeError, ValueError, RuntimeError, KeyError) as exc:
        report = {"status": "error", "error": str(exc)}
        print(json.dumps(report, indent=2))
        return 2

    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        args.output.expanduser().write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    print("Offline descriptive report only; no forecasts or trading actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
