"""Local CSV inspection utility for offline research datasets.

Run from the repository root:
    python backend/examples/local_csv_inspector.py path/to/file.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def inspect_csv(path: Path) -> dict[str, object]:
    """Return basic shape/column information without changing the input."""
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row")
        columns = [name.strip() for name in reader.fieldnames]
        rows = sum(1 for _ in reader)
    return {"file": path.name, "rows": rows, "columns": columns}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", type=Path, help="Path to a local CSV file")
    args = parser.parse_args()
    try:
        summary = inspect_csv(args.csv_path)
    except (OSError, UnicodeError, csv.Error, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, indent=2))
        return 2
    print(json.dumps({"status": "ok", **summary}, indent=2))
    print("Local file only; no network access or external actions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
