"""Confirmed local swing-point labels for descriptive price-structure research."""
from math import isfinite
from numbers import Integral


def find_swing_points(bars: list[dict], left: int = 2, right: int = 2) -> dict:
    """Identify strict local extrema only after all right-side bars are present."""
    for name, window in (("left", left), ("right", right)):
        if not isinstance(window, Integral) or isinstance(window, bool) or window < 1:
            raise ValueError(f"{name} window must be a positive integer")
    left, right = int(left), int(right)
    if not isinstance(bars, list):
        raise TypeError("bars must be a list of OHLC dictionaries")

    highs, lows = [], []
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bars[{index}] must be an object")
        row = {}
        for field in ("high", "low"):
            value = bar.get(field)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"bars[{index}].{field} must be numeric")
            value = float(value)
            if not isfinite(value):
                raise ValueError(f"bars[{index}].{field} must be finite")
            row[field] = value
        if row["low"] > row["high"]:
            raise ValueError(f"bars[{index}].low must be <= high")
        highs.append(row["high"])
        lows.append(row["low"])

    swing_highs, swing_lows = [], []
    for index in range(left, len(bars) - right):
        high_window = highs[index-left:index+right+1]
        low_window = lows[index-left:index+right+1]
        high = highs[index]
        low = lows[index]
        if high == max(high_window) and high_window.count(high) == 1:
            swing_highs.append({
                "index": index,
                "timestamp": bars[index].get("timestamp"),
                "confirmation_index": index + right,
                "confirmation_timestamp": bars[index + right].get("timestamp"),
                "price": high,
            })
        if low == min(low_window) and low_window.count(low) == 1:
            swing_lows.append({
                "index": index,
                "timestamp": bars[index].get("timestamp"),
                "confirmation_index": index + right,
                "confirmation_timestamp": bars[index + right].get("timestamp"),
                "price": low,
            })
    return {
        "confirmed_swing_highs": swing_highs,
        "confirmed_swing_lows": swing_lows,
        "left_bars": left,
        "right_bars": right,
        "confirmation_note": "A swing is labelled only after the right-side confirmation bars exist.",
    }
