"""Rule-based candlestick shape labels for descriptive chart education."""
def classify_candles(bars: list[dict]) -> list[dict]:
    """Return per-bar geometric labels; patterns are observations, not forecasts."""
    results = []
    for index, bar in enumerate(bars):
        o, h, low, c = (float(bar[k]) for k in ("open", "high", "low", "close"))
        span = h - low
        if span <= 0:
            results.append({"index": index, "timestamp": bar.get("timestamp"), "patterns": []})
            continue
        body = abs(c - o)
        upper = h - max(o, c)
        lower = min(o, c) - low
        labels = []
        if body / span <= 0.10:
            labels.append("doji_like")
        if body / span <= 0.30 and lower >= body * 2 and upper <= max(body, span * 0.10):
            labels.append("hammer_shape")
        if body / span <= 0.30 and upper >= body * 2 and lower <= max(body, span * 0.10):
            labels.append("shooting_star_shape")
        if index:
            prev = bars[index - 1]
            po, pc = float(prev["open"]), float(prev["close"])
            if c > o and pc < po and o <= pc and c >= po:
                labels.append("bullish_engulfing_shape")
            elif c < o and pc > po and o >= pc and c <= po:
                labels.append("bearish_engulfing_shape")
            ph, pl = float(prev["high"]), float(prev["low"])
            if h < ph and low > pl:
                labels.append("inside_bar")
        results.append({
            "index": index,
            "timestamp": bar.get("timestamp"),
            "patterns": labels,
        })
    return results
