"""Confirmed local swing-point labels for descriptive price-structure research."""
from math import isfinite
from numbers import Integral, Real


def find_swing_points(bars: list[dict], left: int = 2, right: int = 2) -> dict:
    """Find unique local extrema and report when each becomes observable.

    A pivot at index i is not emitted until i + right exists.
    This is a descriptive historical label, not a same-bar causal feature.
    """
    if (
        not isinstance(left, Integral) or isinstance(left, bool)
        or not isinstance(right, Integral) or isinstance(right, bool)
        or left < 1 or right < 1
    ):
        raise ValueError("left and right windows must be positive integers")
    if not isinstance(bars, (list, tuple)):
        raise ValueError("bars must be a list or tuple of bar objects")

    highs, lows = [], []
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bars[{index}] must be an object")
        row = []
        for field in ("high", "low"):
            value = bar.get(field)
            if isinstance(value, bool) or not isinstance(value, Real):
                raise ValueError(f"bars[{index}].{field} must be numeric")
            value = float(value)
            if not isfinite(value):
                raise ValueError(f"bars[{index}].{field} must be finite")
            row.append(value)
        high, low = row
        if high <= 0 or low <= 0:
            raise ValueError(f"bars[{index}] high and low must be positive")
        if low > high:
            raise ValueError(f"bars[{index}].low must be <= high")
        highs.append(high)
        lows.append(low)

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
        "left_bars": int(left),
        "right_bars": int(right),
        "confirmation_note": "A swing is labelled only after the right-side confirmation bars exist.",
    }
