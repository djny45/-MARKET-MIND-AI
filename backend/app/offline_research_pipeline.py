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
    # Read once, hash these exact bytes, and parse the same immutable snapshot.
    # Re-reading the path before/after parsing can miss a transient edit or
    # associate a digest with rows from a different file version.
    source_snapshot = source_file.read_bytes()
    source_sha256 = hashlib.sha256(source_snapshot).hexdigest()
    frame = load_ohlcv_csv(source_snapshot, timestamp_column=timestamp_column)
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

    if not isinstance(research_result, dict):
        raise ValueError("research_result must be an object")
    source_path = research_result.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("research_result must include source_path provenance")
    source_sha256 = research_result.get("source_sha256")
    if (
        not isinstance(source_sha256, str)
        or len(source_sha256) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in source_sha256)
    ):
        raise ValueError("research_result must include a valid source_sha256")
    # Verify the original source still matches the recorded digest at export
    # time. The DataFrame can remain unchanged while its source CSV is edited.
    try:
        current_source_sha256 = hashlib.sha256(Path(source_path).read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("source CSV is unavailable at evidence export time") from exc
    if current_source_sha256 != source_sha256.lower():
        raise ValueError("source CSV changed after research; rerun before exporting evidence")
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
    # Revalidate ordering at the export boundary because callers can pass
    # a modified DataFrame instead of the untouched loader result.
    import pandas as pd
    try:
        normalized_timestamps = pd.to_datetime(
            frame[timestamp_column], utc=True, errors="raise"
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("dataset timestamps must be valid datetime values") from exc
    if normalized_timestamps.isna().any():
        raise ValueError("dataset timestamps cannot be missing")
    if normalized_timestamps.duplicated().any():
        raise ValueError("dataset timestamps cannot contain duplicates")
    if not normalized_timestamps.is_monotonic_increasing:
        raise ValueError("dataset timestamps must be sorted chronologically")

    # Evidence bars reserve these fields for normalized timestamps and
    # source provenance. Reject collisions rather than silently overwriting
    # user-supplied CSV values during export.
    if "source" in frame.columns:
        raise ValueError("dataset column 'source' conflicts with source provenance")
    if timestamp_column != "timestamp" and "timestamp" in frame.columns:
        raise ValueError(
            "dataset column 'timestamp' conflicts with normalized timestamp "
            "when a different timestamp_column is selected"
        )

    bars = []
    for row in frame.to_dict(orient="records"):
        # CSV blanks in optional metadata columns become pandas NaN. Convert
        # missing scalar values to JSON null before strict evidence export.
        row = {
            key: (None if pd.isna(value) else value)
            for key, value in row.items()
        }
        timestamp = row.pop(timestamp_column)
        if hasattr(timestamp, "isoformat"):
            timestamp = timestamp.isoformat()
        row["timestamp"] = str(timestamp)
        row["source"] = source_path
        bars.append(row)
    history = {
        "bars": bars,
        "source": source_path,
        "sources": [source_path],
        "source_sha256": source_sha256.lower(),
        "status": "offline_csv",
        "retrieved_at": None,
        "first_timestamp": bars[0].get("timestamp") if bars else None,
        "last_timestamp": bars[-1].get("timestamp") if bars else None,
    }
    return build_research_evidence_bundle(symbol, interval, history)
