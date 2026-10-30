"""Timestamped descriptive event timeline for stored OHLCV observations."""
from .candle_patterns import classify_candles
from .swing_points import find_swing_points


def build_research_timeline(history: dict, limit: int = 200) -> dict:
    bars = history.get("bars", [])
    if not isinstance(limit, int) or limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not bars:
        return {"symbol": history.get("symbol"), "interval": history.get("interval"),
                "events": [], "bars_included": 0, "status": "no_stored_observations",
                "execution": "disabled"}
    labels = classify_candles(bars)
    swings = find_swing_points(bars)
    high_by_index = {p["index"]: p for p in swings["confirmed_swing_highs"]}
    low_by_index = {p["index"]: p for p in swings["confirmed_swing_lows"]}
    start = max(0, len(bars) - limit)
    events = []
    for index in range(start, len(bars)):
        bar = bars[index]
        previous = bars[index - 1] if index else None
        close = float(bar["close"])
        change_pct = None
        if previous:
            prior_close = float(previous["close"])
            if prior_close:
                change_pct = round((close / prior_close - 1) * 100, 6)
        kinds = []
        patterns = labels[index]["patterns"]
        if patterns:
            kinds.append({"type": "candle_geometry", "labels": patterns})
        if index in high_by_index:
            kinds.append({"type": "confirmed_swing_high", "price": high_by_index[index]["price"],
                          "confirmation_bars": swings["right_bars"]})
        if index in low_by_index:
            kinds.append({"type": "confirmed_swing_low", "price": low_by_index[index]["price"],
                          "confirmation_bars": swings["right_bars"]})
        events.append({
            "index": index, "timestamp": bar.get("timestamp"),
            "open": float(bar["open"]), "high": float(bar["high"]),
            "low": float(bar["low"]), "close": close,
            "volume": float(bar["volume"]), "close_change_pct": change_pct,
            "source": bar.get("source", "unknown"), "status": bar.get("status", "unknown"),
            "retrieved_at": bar.get("retrieved_at"), "observations": kinds,
        })
    return {
        "symbol": history.get("symbol"), "interval": history.get("interval"),
        "events": events, "bars_included": len(events), "total_bars": len(bars),
        "status": "available", "interpretation": "Historical bar observations and rule-based geometry labels only.",
        "limitations": ["Swing points are labelled only after right-side confirmation bars exist.",
                        "Candle geometry labels are descriptive and not predictive.",
                        "Percentage change is close-to-close and is not a return forecast."],
        "execution": "disabled",
    }
