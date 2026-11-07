"""Shared normalization and validation for optional historical OHLC adapters."""

from __future__ import annotations

from typing import Any


_TIMESTAMP_COLUMNS = ("timestamp", "datetime", "date", "time")
_REQUIRED_OHLC = {"open", "high", "low", "close"}


def normalize_and_validate_ohlc(
    ohlc: Any, *, duplicate_extra_columns: tuple[str, ...] = ()
):
    """Return a normalized OHLC DataFrame with timestamp and price checks.

    Extra columns are permitted unless they are explicitly consumed by an
    adapter. For example, SMC consumes volume for order blocks while TA-Lib
    does not, so the SMC caller includes volume in duplicate-column checks.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "Historical OHLC adapters require optional pandas and numpy dependencies."
        ) from exc

    if not isinstance(ohlc, pd.DataFrame):
        raise TypeError("ohlc must be a pandas DataFrame")

    frame = ohlc.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    relevant_columns = _REQUIRED_OHLC | set(duplicate_extra_columns) | set(_TIMESTAMP_COLUMNS)
    duplicate_columns = set(frame.columns[frame.columns.duplicated(keep=False)])
    relevant_duplicates = sorted(duplicate_columns.intersection(relevant_columns))
    if relevant_duplicates:
        raise ValueError(
            "Duplicate required OHLC/timestamp columns after case/whitespace normalization: "
            f"{relevant_duplicates}"
        )

    timestamp_columns = [column for column in _TIMESTAMP_COLUMNS if column in frame.columns]
    if len(timestamp_columns) > 1:
        raise ValueError("Multiple recognized timestamp columns are ambiguous")
    if timestamp_columns:
        try:
            parsed_timestamps = pd.to_datetime(
                frame[timestamp_columns[0]], utc=True, errors="raise"
            )
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Timestamp column must contain valid datetime values") from exc
        if parsed_timestamps.isna().any():
            raise ValueError("Timestamp column cannot contain missing values")
        if parsed_timestamps.duplicated().any():
            raise ValueError("Timestamp column cannot contain duplicate instants")
        if not parsed_timestamps.is_monotonic_increasing:
            raise ValueError("Timestamp column must be sorted chronologically")

    missing = _REQUIRED_OHLC.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required OHLC columns: {sorted(missing)}")

    for column in _REQUIRED_OHLC:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    values = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("OHLC data contains NaN or infinite values")
    if (values <= 0).any():
        raise ValueError("OHLC prices must be strictly positive")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("OHLC integrity error: high is below an OHLC component")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC integrity error: low is above an OHLC component")
    return frame
