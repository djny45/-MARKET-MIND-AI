"""Offline Smart Money Concepts indicator analysis for historical OHLCV research.

This adapter annotates supplied bars. It does not produce trade instructions,
place orders, connect to brokers, or claim predictive value.
"""
from __future__ import annotations

from typing import Any


def analyze_historical_ohlcv(
    ohlc: Any,
    *,
    swing_length: int = 50,
    join_consecutive_fvg: bool = False,
    close_break: bool = True,
    close_mitigation: bool = False,
    liquidity_range_percent: float = 0.01,
) -> dict[str, Any]:
    """Return SMC indicator tables for an offline, historical OHLC DataFrame.

    Input columns are case-insensitive and must include open/high/low/close.
    The caller is responsible for provenance, timezone, and chronological data.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "SMC research dependencies are optional. Install "
            "backend/requirements-smc-research.txt first."
        ) from exc

    if not isinstance(ohlc, pd.DataFrame):
        raise TypeError("ohlc must be a pandas DataFrame")
    if swing_length < 1:
        raise ValueError("swing_length must be >= 1")
    if not 0 < liquidity_range_percent <= 1:
        raise ValueError("liquidity_range_percent must be in (0, 1]")

    frame = ohlc.copy()
    frame.columns = [str(column).strip().lower() for column in frame.columns]
    required = {"open", "high", "low", "close"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Missing required OHLC columns: {sorted(missing)}")
    if len(frame) < max(5, swing_length * 2 + 1):
        raise ValueError("Not enough bars for the requested swing_length")

    for column in ("open", "high", "low", "close"):
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    values = frame[["open", "high", "low", "close"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("OHLC data contains NaN or infinite values")
    if (frame["high"] < frame[["open", "close", "low"]].max(axis=1)).any():
        raise ValueError("OHLC integrity error: high is below an OHLC component")
    if (frame["low"] > frame[["open", "close", "high"]].min(axis=1)).any():
        raise ValueError("OHLC integrity error: low is above an OHLC component")

    # Import after input validation to keep the core API dependency-light.
    from app.vendor.smartmoneyconcepts import smc

    swings = smc.swing_highs_lows(frame, swing_length=swing_length)
    return {
        "fvg": smc.fvg(frame, join_consecutive=join_consecutive_fvg),
        "swing_highs_lows": swings,
        "bos_choch": smc.bos_choch(
            frame, swings, close_break=close_break
        ),
        "order_blocks": smc.ob(
            frame, swings, close_mitigation=close_mitigation
        ),
        "liquidity": smc.liquidity(
            frame, swings, range_percent=liquidity_range_percent
        ),
        "retracements": smc.retracements(frame, swings),
    }
