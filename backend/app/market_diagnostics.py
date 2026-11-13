"""Descriptive volume, volatility and path diagnostics for OHLCV history."""
from math import isfinite, sqrt


def _numeric_overflow(count, note):
    return {
        "status": "numeric_overflow",
        "bars_analyzed": count,
        "limitations": [note],
    }


def build_market_diagnostics(bars: list[dict], volume_window: int = 20) -> dict:
    if volume_window < 2:
        raise ValueError("volume_window must be at least 2")
    if len(bars) < 3:
        return {
            "status": "insufficient_data",
            "bars_analyzed": len(bars),
            "limitations": ["At least three bars are required for return and volatility diagnostics."],
        }

    try:
        closes = [float(bar["close"]) for bar in bars]
        volumes = [float(bar["volume"]) for bar in bars]
    except (KeyError, TypeError, ValueError, OverflowError):
        return {
            "status": "invalid_data",
            "bars_analyzed": len(bars),
            "limitations": ["Close and volume fields must be present and numeric."],
        }
    if (
        any(not isfinite(value) or value <= 0 for value in closes)
        or any(not isfinite(value) or value < 0 for value in volumes)
    ):
        return {
            "status": "invalid_data",
            "bars_analyzed": len(bars),
            "limitations": ["Close prices must be finite and positive; volume must be finite and non-negative."],
        }

    try:
        returns = [closes[i] / closes[i - 1] - 1 for i in range(1, len(closes))]
        if any(not isfinite(value) for value in returns):
            return _numeric_overflow(len(bars), "A close-to-close return exceeded supported numeric precision.")
        mean_return = sum(returns) / len(returns)
        variance = sum((value - mean_return) ** 2 for value in returns) / (len(returns) - 1)
        volatility = sqrt(variance)

        peak = closes[0]
        max_drawdown = 0.0
        for close in closes:
            peak = max(peak, close)
            max_drawdown = min(max_drawdown, close / peak - 1)

        window = min(volume_window, len(volumes))
        reference = volumes[-window:]
        average_volume = sum(reference) / window
        relative_volume = None if average_volume == 0 else volumes[-1] / average_volume

        regime_sample = returns[-20:] if len(returns) >= 20 else returns
        regime_mean = sum(regime_sample) / len(regime_sample)
        regime_variance = sum(
            (value - regime_mean) ** 2 for value in regime_sample
        ) / max(1, len(regime_sample) - 1)
        regime_volatility = sqrt(regime_variance)
        derived = [
            mean_return, variance, volatility, max_drawdown, average_volume,
            relative_volume, regime_mean, regime_variance, regime_volatility,
        ]
        if any(value is not None and not isfinite(value) for value in derived):
            return _numeric_overflow(len(bars), "A derived market diagnostic exceeded supported numeric precision.")
    except (OverflowError, ZeroDivisionError):
        return _numeric_overflow(len(bars), "Market diagnostic arithmetic exceeded supported numeric precision.")

    if len(regime_sample) < 2:
        volatility_label = "insufficient_data"
    elif regime_volatility < 0.005:
        volatility_label = "lower_observed_volatility"
    elif regime_volatility < 0.02:
        volatility_label = "moderate_observed_volatility"
    else:
        volatility_label = "higher_observed_volatility"

    return {
        "status": "calculated",
        "bars_analyzed": len(bars),
        "returns": {
            "mean_per_observation": round(mean_return, 8),
            "sample_volatility_per_observation": round(volatility, 8),
            "observations": len(returns),
        },
        "volume": {
            "latest": volumes[-1],
            "reference_window": window,
            "reference_average": round(average_volume, 8),
            "relative_to_reference_average": round(relative_volume, 6) if relative_volume is not None else None,
            "note": "Relative volume compares the latest bar with the inclusive trailing reference window.",
        },
        "path": {
            "maximum_close_to_close_drawdown": round(max_drawdown, 8),
            "note": "Historical close-to-close path statistic; not a forecast or risk limit.",
        },
        "volatility_regime": {
            "label": volatility_label,
            "sample_size": len(regime_sample),
            "thresholds_per_observation": {
                "lower_below": 0.005,
                "moderate_below": 0.02,
            },
            "note": "Fixed descriptive thresholds; not annualized and not calibrated across asset classes.",
        },
        "limitations": [
            "No annualization is applied because bar interval and market calendar conventions differ.",
            "Volume comparability depends on instrument and provider conventions.",
            "The volatility labels are descriptive thresholds, not forecasts.",
        ],
    }
