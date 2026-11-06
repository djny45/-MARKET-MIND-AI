"""Offline CSV loader for educational historical OHLCV analysis.

This module reads local files only. It does not fetch data, connect to
TradingView/exchanges/brokers, generate trade signals, or place orders.
"""
from __future__ import annotations

from pathlib import Path
import csv
import re
from typing import Any

REQUIRED_COLUMNS = ("open", "high", "low", "close")
OPTIONAL_COLUMNS = ("volume",)


def load_ohlcv_csv(path: str | Path, *, timestamp_column: str | None = None) -> Any:
    """Load and validate a local OHLCV CSV into a pandas DataFrame.

    Column names are normalized to lowercase. If a timestamp column is
    supplied, every value must include an explicit timezone offset (not a
    numeric epoch or timezone-naive timestamp). Values are normalized to UTC
    and rows sorted chronologically. Duplicate/missing timestamps are rejected.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Install pandas and numpy to use offline CSV research.") from exc

    if timestamp_column is not None and (
        not isinstance(timestamp_column, str) or not timestamp_column.strip()
    ):
        raise ValueError("timestamp_column must be a non-empty string or None")

    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"CSV file does not exist: {source}")
    # Inspect the literal header before pandas renames blank fields to
    # generated names such as "Unnamed: 4".
    try:
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            if header is not None:
                for row_number, row in enumerate(reader, start=2):
                    if not row:
                        raise ValueError(f"CSV contains a blank row at line {row_number}")
                    if len(row) != len(header):
                        raise ValueError(
                            f"CSV row {row_number} has {len(row)} fields; "
                            f"expected {len(header)}"
                        )
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Could not read CSV: {exc}") from exc
    if not header or all(not str(name).strip() for name in header):
        raise ValueError("CSV must include a non-empty header row")
    if any(not str(name).strip() for name in header):
        raise ValueError("CSV contains an empty column name")
    normalized_header = [str(name).strip().lower() for name in header]
    if len(set(normalized_header)) != len(normalized_header):
        raise ValueError("CSV contains duplicate columns after normalization")

    try:
        frame = pd.read_csv(source)
    except (UnicodeError, OSError, pd.errors.ParserError) as exc:
        raise ValueError(f"Could not parse CSV data: {exc}") from exc
    if frame.empty:
        raise ValueError("CSV dataset is empty")

    frame.columns = [str(column).strip().lower() for column in frame.columns]
    if any(not column for column in frame.columns):
        raise ValueError("CSV contains an empty column name after normalization")
    if len(set(frame.columns)) != len(frame.columns):
        raise ValueError("CSV contains duplicate columns after normalization")

    missing = set(REQUIRED_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required OHLC columns: {sorted(missing)}")

    for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="raise")

    numeric_columns = [
        column for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS
        if column in frame.columns
    ]
    values = frame[numeric_columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Dataset contains NaN or infinite numeric values")
    if (frame[list(REQUIRED_COLUMNS)] <= 0).any().any():
        raise ValueError("OHLC prices must be strictly positive")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("OHLC integrity error: high is below an OHLC component")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC integrity error: low is above an OHLC component")
    if "volume" in frame.columns and (frame["volume"] < 0).any():
        raise ValueError("Volume must be non-negative")

    if timestamp_column is not None:
        timestamp_column = timestamp_column.strip().lower()
        if timestamp_column not in frame.columns:
            raise ValueError(f"Timestamp column not found: {timestamp_column}")
        if timestamp_column in REQUIRED_COLUMNS or timestamp_column in OPTIONAL_COLUMNS:
            raise ValueError("Timestamp column cannot be an OHLCV field")
        if pd.api.types.is_numeric_dtype(frame[timestamp_column]):
            raise ValueError(
                "Numeric timestamps are ambiguous; convert epoch values to "
                "ISO-8601 timestamps with an explicit timezone before import"
            )
        raw_timestamps = frame[timestamp_column].astype("string").str.strip()
        if raw_timestamps.isna().any() or raw_timestamps.eq("").any():
            raise ValueError("Missing timestamps are not allowed")
        timezone_suffix = re.compile(r"(?:Z|[+-]\d{2}:?\d{2})$", re.IGNORECASE)
        naive = ~raw_timestamps.map(lambda value: bool(timezone_suffix.search(value)))
        if naive.any():
            raise ValueError(
                "Timezone-naive timestamps are ambiguous; add an explicit "
                "ISO-8601 timezone offset (for example Z or +05:30)"
            )
        parsed = pd.to_datetime(raw_timestamps, utc=True, errors="raise")
        if parsed.isna().any():
            raise ValueError("Missing timestamps are not allowed")
        if parsed.duplicated().any():
            raise ValueError("Duplicate timestamps are not allowed")
        frame[timestamp_column] = parsed
        frame = frame.sort_values(timestamp_column, kind="stable").reset_index(drop=True)

    return frame
