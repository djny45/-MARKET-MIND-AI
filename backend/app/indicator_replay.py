"""Prefix-replay checks for causal indicator calculations; no predictive evaluation."""
import math

from . import indicators


def _same_value(actual, expected, tolerance=1e-9):
    if actual is None or expected is None:
        return actual is None and expected is None
    return math.isfinite(actual) and math.isfinite(expected) and math.isclose(
        actual, expected, rel_tol=tolerance, abs_tol=tolerance
    )


def build_indicator_replay_report(history, checkpoints=8):
    """Replay each provider history independently; never interleave provider bars."""
    bars = history.get("bars", [])
    source_groups = {}
    for bar in bars:
        source_groups.setdefault(str(bar.get("source") or "unknown"), []).append(bar)
    if len(source_groups) > 1:
        reports = {}
        for source, source_bars in sorted(source_groups.items()):
            if len(source_bars) < 2:
                reports[source] = {
                    "mode": "historical_prefix_replay", "source": source,
                    "status": "insufficient_source_history", "bars_replayed": len(source_bars),
                    "checkpoint_count": 0, "indicator_comparison_count": 0,
                    "mismatch_count": 0, "causal_consistency": "not_evaluated",
                    "comparisons": [],
                }
                continue
            reports[source] = build_indicator_replay_report(
                {**history, "bars": source_bars}, checkpoints
            )
            reports[source]["source"] = source
            reports[source]["status"] = "evaluated"
        evaluated = [item for item in reports.values() if item["status"] == "evaluated"]
        mismatch_count = sum(item["mismatch_count"] for item in evaluated)
        return {
            "mode": "source_isolated_historical_prefix_replay",
            "symbol": history.get("symbol"), "interval": history.get("interval"),
            "bars_replayed": len(bars), "source_count": len(reports),
            "evaluated_source_count": len(evaluated),
            "checkpoint_count": sum(item["checkpoint_count"] for item in evaluated),
            "indicator_comparison_count": sum(item["indicator_comparison_count"] for item in evaluated),
            "mismatch_count": mismatch_count,
            "causal_consistency": (
                "not_evaluated" if not evaluated else
                "pass" if mismatch_count == 0 else "review_required"
            ),
            "source_reports": reports,
            "limitations": [
                "Each source is replayed independently; observations from different providers are never interleaved into one indicator series.",
                "Sources with fewer than two observations are reported as insufficient_source_history.",
                "Checks prefix reproducibility, not formula correctness, provider authenticity, licensing or predictive accuracy.",
            ],
        }
    if not isinstance(bars, list) or len(bars) < 2:
        raise ValueError("At least two historical bars are required for replay.")
    if len(bars) > 5000:
        raise ValueError("Replay is limited to 5000 bars.")
    if not isinstance(checkpoints, int) or isinstance(checkpoints, bool) or not 2 <= checkpoints <= 20:
        raise ValueError("checkpoints must be an integer between 2 and 20.")

    closes = []
    for index, bar in enumerate(bars):
        try:
            close = float(bar["close"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Bar {index} has a missing or invalid close.") from exc
        if not math.isfinite(close) or close <= 0:
            raise ValueError(f"Bar {index} close must be finite and positive.")
        closes.append(close)

    sma_period = min(20, len(closes))
    ema_period = min(20, len(closes))
    rsi_period = min(14, len(closes) - 1)
    full_sma = indicators.sma(closes, sma_period)
    full_ema = indicators.ema(closes, ema_period)
    full_rsi = indicators.rsi(closes, rsi_period)
    full_macd = indicators.macd(closes)
    full_bollinger = indicators.bollinger(closes, sma_period)

    candidate_indices = {
        max(1, round(position * (len(closes) - 1) / (checkpoints - 1)))
        for position in range(checkpoints)
    }
    indices = sorted(candidate_indices)
    comparisons = []
    mismatch_count = 0
    for index in indices:
        prefix = closes[:index + 1]
        prefix_sma = indicators.sma(prefix, sma_period)[-1]
        prefix_ema = indicators.ema(prefix, ema_period)[-1]
        prefix_rsi_values = indicators.rsi(prefix, rsi_period)
        prefix_rsi = prefix_rsi_values[-1] if prefix_rsi_values else None
        prefix_macd = indicators.macd(prefix)
        prefix_bollinger = indicators.bollinger(prefix, sma_period)
        expected_rsi = full_rsi[index - 1]
        actual_values = {
            "sma": prefix_sma,
            "ema": prefix_ema,
            "rsi": prefix_rsi,
            "macd": prefix_macd["macd"][-1],
            "macd_signal": prefix_macd["signal"][-1],
            "bollinger_upper": prefix_bollinger["upper"][-1],
            "bollinger_middle": prefix_bollinger["middle"][-1],
            "bollinger_lower": prefix_bollinger["lower"][-1],
        }
        expected_values = {
            "sma": full_sma[index],
            "ema": full_ema[index],
            "rsi": expected_rsi,
            "macd": full_macd["macd"][index],
            "macd_signal": full_macd["signal"][index],
            "bollinger_upper": full_bollinger["upper"][index],
            "bollinger_middle": full_bollinger["middle"][index],
            "bollinger_lower": full_bollinger["lower"][index],
        }
        mismatches = [
            name for name in actual_values
            if not _same_value(actual_values[name], expected_values[name])
        ]
        mismatch_count += len(mismatches)
        comparisons.append({
            "bar_index": index,
            "timestamp": bars[index].get("timestamp"),
            "prefix_observation_count": index + 1,
            "values": actual_values,
            "compared_indicators": len(actual_values),
            "indicator_values": actual_values,
            "mismatch_count": len(mismatches),
            "mismatched_indicators": mismatches,
        })

    return {
        "mode": "historical_prefix_replay",
        "symbol": history.get("symbol"),
        "interval": history.get("interval"),
        "bars_replayed": len(bars),
        "periods": {
            "sma": sma_period,
            "ema": ema_period,
            "rsi": rsi_period,
            "macd": {"fast": 12, "slow": 26, "signal": 9},
        },
        "checkpoint_count": len(comparisons),
        "indicator_comparison_count": sum(item["compared_indicators"] for item in comparisons),
        "mismatch_count": mismatch_count,
        "causal_consistency": "pass" if mismatch_count == 0 else "review_required",
        "comparisons": comparisons,
        "limitations": [
            "Checks prefix reproducibility at selected checkpoints; they do not prove formula correctness or predictive accuracy.",
            "Only close-price indicators are evaluated; source authenticity and licensing are not verified.",
            "No missing observations are inferred and no forecasts, recommendations or orders are produced.",
        ],
    }
