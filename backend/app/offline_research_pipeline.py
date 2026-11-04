"""Offline orchestration for local OHLCV indicator research.

This module consumes a local CSV and invokes optional indicator adapters.
It intentionally contains no network, broker, exchange, or order functionality.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.offline_dataset import load_ohlcv_csv


def run_offline_research(
    csv_path: str | Path,
    *,
    timestamp_column: str | None = None,
    include_ta_lib: bool = False,
    include_smc: bool = False,
    smc_swing_length: int = 50,
) -> dict[str, Any]:
    """Load a local CSV and optionally calculate offline indicator annotations.

    Optional indicator packages are imported only when requested. Returned
    arrays/tables are research annotations, not trading signals or advice.
    """
    frame = load_ohlcv_csv(csv_path, timestamp_column=timestamp_column)
    result: dict[str, Any] = {
        "row_count": len(frame),
        "columns": list(frame.columns),
        "dataset": frame,
        "indicators": {},
    }

    if include_ta_lib:
        from app.ta_lib_research import analyze_historical_ohlcv
        result["indicators"]["ta_lib"] = analyze_historical_ohlcv(frame)

    if include_smc:
        from app.smc_research import analyze_historical_ohlcv
        result["indicators"]["smc"] = analyze_historical_ohlcv(
            frame, swing_length=smc_swing_length
        )

    return result
