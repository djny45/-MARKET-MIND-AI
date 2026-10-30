"""Deterministic descriptive chart research over stored OHLCV observations."""
from . import indicators
from .candle_patterns import classify_candles
from .swing_points import find_swing_points


def build_chart_report(history: dict) -> dict:
    bars = history.get("bars", [])
    if len(bars) < 2:
        raise ValueError("At least two stored bars are required for chart research.")
    closes = [float(bar["close"]) for bar in bars]
    highs = [float(bar["high"]) for bar in bars]
    lows = [float(bar["low"]) for bar in bars]
    if any(value <= 0 for value in closes + highs + lows):
        raise ValueError("Stored OHLC prices must be positive.")

    latest = closes[-1]
    sma20 = indicators.sma(closes, min(20, len(closes)))[-1]
    sma50 = indicators.sma(closes, min(50, len(closes)))[-1]
    rsi_values = indicators.rsi(closes, min(14, len(closes) - 1))
    rsi_latest = rsi_values[-1] if rsi_values else None
    macd = indicators.macd(closes)
    bb = indicators.bollinger(closes, min(20, len(closes)))
    true_ranges = []
    for index, bar in enumerate(bars):
        previous_close = closes[index - 1] if index else float(bar["open"])
        true_ranges.append(max(
            highs[index] - lows[index],
            abs(highs[index] - previous_close),
            abs(lows[index] - previous_close),
        ))
    atr_period = min(14, len(true_ranges))
    atr = sum(true_ranges[-atr_period:]) / atr_period
    window = min(20, len(bars))
    support = min(lows[-window:])
    resistance = max(highs[-window:])

    if latest > sma20 and sma20 > sma50:
        regime = "close_above_short_and_medium_average"
    elif latest < sma20 and sma20 < sma50:
        regime = "close_below_short_and_medium_average"
    else:
        regime = "mixed_or_sideways_average_structure"

    swing_structure = find_swing_points(bars, left=2, right=2)
    candle_labels = classify_candles(bars)
    recent_candle_labels = [
        item for item in candle_labels[-10:] if item["patterns"]
    ]
    sources = sorted({bar.get("source", "unknown") for bar in bars})
    statuses = sorted({bar.get("status", "unknown") for bar in bars})
    warnings = []
    if "synthetic" in statuses:
        warnings.append("Dataset includes synthetic fixture observations; this is not market evidence.")
    if len(bars) < 50:
        warnings.append("Fewer than 50 bars: medium-term averages use the available sample.")
    if len(sources) > 1:
        warnings.append("Multiple data sources are present; inspect source consistency before interpretation.")

    return {
        "mode": "descriptive_research_only",
        "symbol": history.get("symbol"),
        "interval": history.get("interval"),
        "bars_analyzed": len(bars),
        "latest_bar_timestamp": bars[-1].get("timestamp"),
        "latest_close": latest,
        "indicators": {
            "sma20": round(sma20, 8),
            "sma50": round(sma50, 8),
            "rsi14": round(rsi_latest, 4) if rsi_latest is not None else None,
            "macd": round(macd["macd"][-1], 8),
            "macd_signal": round(macd["signal"][-1], 8),
            "macd_histogram": round(macd["histogram"][-1], 8),
            "bollinger_upper": round(bb["upper"][-1], 8),
            "bollinger_middle": round(bb["middle"][-1], 8),
            "bollinger_lower": round(bb["lower"][-1], 8),
            "atr14": round(atr, 8),
        },
        "swing_structure": swing_structure,
        "candlestick_observations": {
            "latest_bar": candle_labels[-1],
            "recent_pattern_labels": recent_candle_labels,
            "method_note": "Rule-based candle geometry labels; not standalone predictive signals.",
        },
        "observed_structure": {
            "moving_average_regime": regime,
            "recent_window_bars": window,
            "recent_low_reference": support,
            "recent_high_reference": resistance,
        },
        "provenance": {
            "sources": sources,
            "statuses": statuses,
            "retrieved_at": sorted({bar.get("retrieved_at") for bar in bars if bar.get("retrieved_at")}),
        },
        "warnings": warnings,
        "interpretation": "Descriptive indicators and recent range references only; not a directional signal, trade recommendation, or forecast.",
        "execution": "disabled",
    }
