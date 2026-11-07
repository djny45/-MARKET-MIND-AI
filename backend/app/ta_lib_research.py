"""Offline TA-Lib indicator annotations for supplied historical OHLCV data.

Research only: this module does not fetch market data, emit trade instructions,
connect to exchanges/brokers, or execute orders.
"""
from __future__ import annotations

from numbers import Integral
from typing import Any


def analyze_historical_ohlcv(
    ohlc: Any,
    *,
    rsi_period: int = 14,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    atr_period: int = 14,
    bbands_period: int = 20,
) -> dict[str, Any]:
    """Calculate standard TA-Lib indicators from an OHLC DataFrame.

    Columns are case-insensitive. Results are arrays aligned to the input rows;
    initial lookback rows naturally contain NaN. The caller must ensure data
    provenance, chronological ordering, timeframe consistency, and point-in-time
    availability before conducting any historical evaluation.
    """
    try:
        import numpy as np
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError(
            "TA-Lib research dependencies are optional. Install "
            "backend/requirements-ta-lib-research.txt first."
        ) from exc

    periods = (rsi_period, fast_period, slow_period, signal_period, atr_period, bbands_period)
    if any(not isinstance(period, Integral) or isinstance(period, bool) for period in periods):
        raise ValueError("Indicator periods must be integers >= 2")
    periods = tuple(int(period) for period in periods)
    rsi_period, fast_period, slow_period, signal_period, atr_period, bbands_period = periods
    if min(periods) < 2:
        raise ValueError("Indicator periods must be integers >= 2")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")

    from app.ohlcv_validation import normalize_and_validate_ohlc

    periods = (rsi_period, fast_period, slow_period, signal_period, atr_period, bbands_period)
    if any(not isinstance(period, Integral) or isinstance(period, bool) for period in periods):
        raise ValueError("Indicator periods must be integers >= 2")
    periods = tuple(int(period) for period in periods)
    rsi_period, fast_period, slow_period, signal_period, atr_period, bbands_period = periods
    if min(periods) < 2:
        raise ValueError("Indicator periods must be integers >= 2")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be less than slow_period")

    frame = normalize_and_validate_ohlc(ohlc)
    # Load TA-Lib only after input validation. This lets the adapter's
    # validation path remain testable when optional indicator binaries are
    # unavailable; calculations still require the TA-Lib package.
    try:
        import talib
    except ImportError as exc:
        raise RuntimeError(
            "TA-Lib research dependencies are optional. Install "
            "backend/requirements-ta-lib-research.txt first."
        ) from exc

    high = frame["high"].to_numpy(dtype=np.float64)
    low = frame["low"].to_numpy(dtype=np.float64)
    close = frame["close"].to_numpy(dtype=np.float64)

    macd, macd_signal, macd_hist = talib.MACD(
        close, fastperiod=fast_period, slowperiod=slow_period,
        signalperiod=signal_period,
    )
    upper, middle, lower = talib.BBANDS(close, timeperiod=bbands_period)
    return {
        "rsi": talib.RSI(close, timeperiod=rsi_period),
        "macd": macd,
        "macd_signal": macd_signal,
        "macd_histogram": macd_hist,
        "atr": talib.ATR(high, low, close, timeperiod=atr_period),
        "sma_20": talib.SMA(close, timeperiod=20),
        "ema_20": talib.EMA(close, timeperiod=20),
        "bbands_upper": upper,
        "bbands_middle": middle,
        "bbands_lower": lower,
    }
