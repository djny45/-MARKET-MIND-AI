"""Offline orchestration for local OHLCV indicator research.

This module consumes a local CSV and invokes optional indicator adapters.
It intentionally contains no network, broker, exchange, or order functionality.
"""
from __future__ import annotations

from pathlib import Path
import hashlib
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

    source_file = Path(csv_path).expanduser().resolve()
    source_sha256 = hashlib.sha256(source_file.read_bytes()).hexdigest()
    frame = load_ohlcv_csv(source_file, timestamp_column=timestamp_column)
    result: dict[str, Any] = {
        "source_path": str(source_file),
        "source_sha256": source_sha256,
        "row_count": len(frame),
        "columns": list(frame.columns),
        "timestamp_column": timestamp_column.strip().lower() if timestamp_column else None,
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


def build_offline_evidence_bundle(
    research_result: dict[str, Any],
    *,
    symbol: str,
    interval: str,
) -> dict[str, Any]:
    """Create a provenance-linked evidence bundle from an offline CSV result.

    This adapter preserves the source CSV hash and source path in the export.
    It only packages historical observations; it does not generate signals.
    """
    from app.research_export import build_research_evidence_bundle

    frame = research_result.get("dataset")
    if frame is None or not hasattr(frame, "to_dict"):
        raise ValueError("research_result must contain a pandas dataset")
    declared_timestamp = research_result.get("timestamp_column")
    if isinstance(declared_timestamp, str) and declared_timestamp in frame.columns:
        timestamp_column = declared_timestamp
    else:
        timestamp_columns = [
            column for column in frame.columns
            if str(column).strip().lower() in {"timestamp", "datetime", "date", "time"}
        ]
        if len(timestamp_columns) != 1:
            raise ValueError("dataset must contain exactly one recognized timestamp column")
        timestamp_column = timestamp_columns[0]
    bars = []
    for row in frame.to_dict(orient="records"):
        timestamp = row.pop(timestamp_column)
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()
        row["timestamp"] = str(timestamp)
        row["source"] = str(research_result.get("source_path") or "offline_csv")
        bars.append(row)
    history = {
        "bars": bars,
        "source": research_result.get("source_path"),
        "sources": [research_result.get("source_path")] if research_result.get("source_path") else [],
        "source_sha256": research_result.get("source_sha256"),
        "status": "offline_csv",
        "retrieved_at": None,
        "first_timestamp": bars[0].get("timestamp") if bars else None,
        "last_timestamp": bars[-1].get("timestamp") if bars else None,
    }
    return build_research_evidence_bundle(symbol, interval, history)
