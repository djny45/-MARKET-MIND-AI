"""Confirmed local swing-point labels for descriptive price-structure research."""
def find_swing_points(bars: list[dict], left: int = 2, right: int = 2) -> dict:
    if left < 1 or right < 1:
        raise ValueError("left and right windows must be positive")
    highs = [float(bar["high"]) for bar in bars]
    lows = [float(bar["low"]) for bar in bars]
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
