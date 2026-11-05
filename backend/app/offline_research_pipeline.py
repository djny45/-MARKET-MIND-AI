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

    Indicator analysis requires a timestamp column so the dataset is parsed
    and sorted chronologically before calculations. Optional indicator packages
    are imported only when requested. Returned arrays/tables are research
    annotations, not trading signals or advice.
    """
    if (include_ta_lib or include_smc) and timestamp_column is None:
        raise ValueError(
            "timestamp_column is required when indicator analysis is enabled "
            "to ensure chronological ordering"
        )

    frame = load_ohlcv_csv(csv_path, timestamp_column=timestamp_column)
    result: dict[str, Any] = {
        "source_path": str(Path(csv_path).expanduser().resolve()),
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
