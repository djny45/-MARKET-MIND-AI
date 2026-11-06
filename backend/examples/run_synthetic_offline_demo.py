"""Run a small offline OHLCV validation demo using synthetic data only.

From the repository root:
    python backend/examples/run_synthetic_offline_demo.py

No external data, APIs, exchange connections, or trading actions are used.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.offline_research_pipeline import run_offline_research  # noqa: E402


def main() -> int:
    sample = BACKEND_DIR / "examples" / "synthetic_ohlcv.csv"
    try:
        result = run_offline_research(sample, timestamp_column="timestamp")
    except RuntimeError as exc:
        print(f"Offline demo unavailable: {exc}", file=sys.stderr)
        return 2

    print("OFFLINE RESEARCH DEMO — SYNTHETIC DATA ONLY")
    print(f"Dataset: {sample.relative_to(REPO_ROOT)}")
    print(f"Rows validated: {result['row_count']}")
    print(f"Columns: {', '.join(result['columns'])}")
    print("Indicator adapters: disabled (dataset-validation demonstration)")
    print("No predictions, recommendations, or trades were generated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
