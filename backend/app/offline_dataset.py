"""Offline CSV loader for educational historical OHLCV analysis.

This module reads local files only. It does not fetch data, connect to
TradingView/exchanges/brokers, generate trade signals, or place orders.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

REQUIRED_COLUMNS = ("open", "high", "low", "close")
OPTIONAL_COLUMNS = ("volume",)


def load_ohlcv_csv(path: str | Path, *, timestamp_column: str | None = None) -> Any:
    """Load and validate a local OHLCV CSV into a pandas DataFrame.

    Column names are normalized to lowercase. If ``timestamp_column`` is
    supplied, it is parsed as UTC and rows are sorted chronologically.
    Duplicate timestamps and malformed OHLC rows are rejected.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("Install pandas and numpy to use offline CSV research.") from exc

    source = Path(path).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"CSV file does not exist: {source}")
    frame = pd.read_csv(source)
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

    numeric_columns = [column for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS
                       if column in frame.columns]
    values = frame[numeric_columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Dataset contains NaN or infinite numeric values")
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
        frame[timestamp_column] = pd.to_datetime(
            frame[timestamp_column], utc=True, errors="raise"
        )
        if frame[timestamp_column].duplicated().any():
            raise ValueError("Duplicate timestamps are not allowed")
        frame = frame.sort_values(timestamp_column, kind="stable").reset_index(drop=True)

    return frame
