"""Timestamped descriptive event timeline for stored OHLCV observations."""
import math

from .candle_patterns import classify_candles
from .swing_points import find_swing_points
from .indicators import sma, rsi, macd


def _validate_ohlcv_bars(bars):
    """Reject malformed OHLCV before indicator math can emit misleading values."""
    required = ("open", "high", "low", "close", "volume")
    for index, bar in enumerate(bars):
        if not isinstance(bar, dict):
            raise ValueError(f"bars[{index}] must be an object")
        values = {}
        for field in required:
            raw = bar.get(field)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise ValueError(f"bars[{index}].{field} must be numeric")
            value = float(raw)
            if not math.isfinite(value):
                raise ValueError(f"bars[{index}].{field} must be finite")
            if field != "volume" and value <= 0:
                raise ValueError(f"bars[{index}].{field} must be positive")
            values[field] = value
        if values["low"] > values["high"]:
            raise ValueError(f"bars[{index}] low must be <= high")
        if values["low"] > min(values["open"], values["close"]):
            raise ValueError(f"bars[{index}] low must be <= open and close")
        if values["high"] < max(values["open"], values["close"]):
            raise ValueError(f"bars[{index}] high must be >= open and close")
        if values["volume"] < 0:
            raise ValueError(f"bars[{index}].volume must be non-negative")

    # Require chronological, unique timestamps when all bars provide them.
    timestamps = [bar.get("timestamp") for bar in bars]
    if any(value is not None for value in timestamps):
        if any(value is None for value in timestamps):
            raise ValueError("timestamps must be present on every bar or none")
        from datetime import datetime, timezone
        parsed = []
        for index, value in enumerate(timestamps):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"bars[{index}].timestamp must be a non-empty string")
            normalized = value.strip()
            if normalized.endswith("Z"):
                normalized = normalized[:-1] + "+00:00"
            try:
                instant = datetime.fromisoformat(normalized)
            except (TypeError, ValueError, OverflowError) as exc:
                raise ValueError("timestamps must be valid timezone-aware ISO datetimes") from exc
            if instant.tzinfo is None:
                raise ValueError(f"bars[{index}].timestamp must include timezone")
            parsed.append(instant.astimezone(timezone.utc))
        if len(set(parsed)) != len(parsed):
            raise ValueError("timestamps must be unique")
        if parsed != sorted(parsed):
            raise ValueError("timestamps must be sorted chronologically")


def build_research_timeline(history: dict, limit: int = 200) -> dict:
    bars = history.get("bars", [])
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 1000:
        raise ValueError("limit must be between 1 and 1000")
    if not bars:
        return {"symbol": history.get("symbol"), "interval": history.get("interval"),
                "events": [], "bars_included": 0, "status": "no_stored_observations",
                "execution": "disabled"}
    _validate_ohlcv_bars(bars)
    labels = classify_candles(bars)
    closes = [float(bar['close']) for bar in bars]
    sma20 = sma(closes, 20)
    rsi_values = rsi(closes, 14)
    macd_values = macd(closes)
    swings = find_swing_points(bars)
    high_by_index = {p["confirmation_index"]: p for p in swings["confirmed_swing_highs"]}
    low_by_index = {p["confirmation_index"]: p for p in swings["confirmed_swing_lows"]}
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
                raw_change_pct = (close / prior_close - 1) * 100
                if math.isfinite(raw_change_pct):
                    change_pct = round(raw_change_pct, 6)
        kinds = []
        patterns = labels[index]["patterns"]
        if patterns:
            kinds.append({"type": "candle_geometry", "labels": patterns})
        if index in high_by_index:
            swing = high_by_index[index]
            kinds.append({
                "type": "confirmed_swing_high",
                "price": swing["price"],
                "pivot_index": swing["index"],
                "pivot_timestamp": swing["timestamp"],
                "confirmation_index": swing["confirmation_index"],
                "confirmation_timestamp": swing["confirmation_timestamp"],
                "confirmation_bars": swings["right_bars"],
            })
        if index in low_by_index:
            swing = low_by_index[index]
            kinds.append({
                "type": "confirmed_swing_low",
                "price": swing["price"],
                "pivot_index": swing["index"],
                "pivot_timestamp": swing["timestamp"],
                "confirmation_index": swing["confirmation_index"],
                "confirmation_timestamp": swing["confirmation_timestamp"],
                "confirmation_bars": swings["right_bars"],
            })
        events.append({
            "index": index, "timestamp": bar.get("timestamp"),
            "open": float(bar["open"]), "high": float(bar["high"]),
            "low": float(bar["low"]), "close": close,
            "volume": float(bar["volume"]), "close_change_pct": change_pct,
            "indicator_context": {
                "sma20": round(sma20[index], 8) if index >= 19 else None,
                "rsi14": round(rsi_values[index - 1], 4) if index > 0 and rsi_values[index - 1] is not None else None,
                "macd": round(macd_values["macd"][index], 8),
                "macd_signal": round(macd_values["signal"][index], 8),
                "macd_histogram": round(macd_values["histogram"][index], 8),
            },
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

