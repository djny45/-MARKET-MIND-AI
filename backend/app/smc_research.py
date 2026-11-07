"""Offline Smart Money Concepts indicator analysis for historical OHLCV research.

This adapter annotates supplied bars. It does not produce trade instructions,
place orders, connect to brokers, or claim predictive value.
"""
from __future__ import annotations

from numbers import Real
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
    """Return SMC indicator tables and explicit temporal-validity metadata.

    Input columns are case-insensitive and must include open/high/low/close.
    The caller is responsible for provenance, timezone, and chronological data.

    Important: SMC swing detection uses swing_length bars both before and
    after a candidate bar. Swing-derived outputs therefore contain look-ahead
    information relative to the candidate bar. Do not use them as same-bar
    features in a causal backtest; shift them to their confirmation timestamp
    or use a separately implemented causal detector.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "SMC research dependencies are optional. Install "
            "backend/requirements-smc-research.txt first."
        ) from exc

    if not isinstance(swing_length, Integral) or isinstance(swing_length, bool) or swing_length < 1:
        raise ValueError("swing_length must be a positive integer")
    if isinstance(liquidity_range_percent, bool) or not isinstance(liquidity_range_percent, Real):
        raise ValueError("liquidity_range_percent must be a finite number in (0, 1]")
    try:
        liquidity_range_percent = float(liquidity_range_percent)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("liquidity_range_percent must be a finite number in (0, 1]") from exc
    if not np.isfinite(liquidity_range_percent) or not 0 < liquidity_range_percent <= 1:
        raise ValueError("liquidity_range_percent must be a finite number in (0, 1]")

    from app.ohlcv_validation import normalize_and_validate_ohlc

    frame = normalize_and_validate_ohlc(
        ohlc, duplicate_extra_columns=("volume",)
    )
    if len(frame) < max(5, swing_length * 2 + 1):
        raise ValueError("Not enough bars for the requested swing_length")

    for column in ("open", "high", "low", "close"):
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

    has_volume = "volume" in frame.columns
    if has_volume:
        frame["volume"] = pd.to_numeric(frame["volume"], errors="raise")
        volume = frame["volume"].to_numpy(dtype=float)
        if not np.isfinite(volume).all():
            raise ValueError("Volume contains NaN or infinite values")
        if (volume < 0).any():
            raise ValueError("Volume must be non-negative")

    # Import after input validation to keep the core API dependency-light.
    from app.vendor.smartmoneyconcepts import smc

    swings = smc.swing_highs_lows(frame, swing_length=swing_length)
    results = {
        "fvg": smc.fvg(frame, join_consecutive=join_consecutive_fvg),
        "swing_highs_lows": swings,
        "bos_choch": smc.bos_choch(
            frame, swings, close_break=close_break
        ),
        "order_blocks": (
            smc.ob(frame, swings, close_mitigation=close_mitigation)
            if has_volume else None
        ),
        "liquidity": smc.liquidity(
            frame, swings, range_percent=liquidity_range_percent
        ),
        "retracements": smc.retracements(frame, swings),
    }

    # Vendor outputs use a RangeIndex. Restore the caller's index so results
    # can be joined to timestamp-indexed source bars without positional drift.
    for name, table in results.items():
        if table is None:
            continue
        if not isinstance(table, (pd.DataFrame, pd.Series)):
            raise TypeError(f"SMC indicator {name!r} did not return a pandas table")
        if len(table) != len(frame):
            raise ValueError(
                f"SMC indicator {name!r} returned {len(table)} rows; "
                f"expected {len(frame)}"
            )
        table.index = frame.index

    skipped = {}
    if not has_volume:
        skipped["order_blocks"] = "requires a volume column; omitted without fabrication"

    results["research_metadata"] = {
        "indicator_family": "smart_money_concepts",
        "research_only": True,
        "lookahead_bias_possible": True,
        "swing_confirmation_bars": swing_length,
        "skipped_indicators": skipped,
        "warning": (
            "Swing-derived annotations require future bars for confirmation. "
            "Do not use candidate-bar values as causal same-bar backtest "
            "features; align them to their confirmation timestamp."
        ),
    }
    return results
