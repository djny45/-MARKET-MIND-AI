"""Timestamp-aligned descriptive market breadth from stored close series."""


def build_market_breadth_report(histories: dict[str, dict], min_symbols: int = 2) -> dict:
    """Summarize positive/negative/unchanged returns at each exact shared timestamp."""
    if min_symbols < 2:
        raise ValueError("min_symbols must be at least 2")
    if len(histories) < 2:
        raise ValueError("at least two symbols are required")

    returns_by_symbol = {}
    for raw_symbol, history in histories.items():
        symbol = str(raw_symbol).strip().upper()
        if not symbol:
            continue
        closes = {}
        for bar in history.get("bars", []):
            timestamp = bar.get("timestamp")
            try:
                close = float(bar["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if timestamp and close > 0:
                closes[str(timestamp)] = close
        ordered = sorted(closes.items())
        returns_by_symbol[symbol] = {
            ordered[index][0]: ordered[index][1] / ordered[index - 1][1] - 1
            for index in range(1, len(ordered))
            if ordered[index - 1][1] > 0
        }

    timestamps = sorted({
        timestamp
        for observations in returns_by_symbol.values()
        for timestamp in observations
    })
    breadth = []
    for timestamp in timestamps:
        values = {
            symbol: observations[timestamp]
            for symbol, observations in returns_by_symbol.items()
            if timestamp in observations
        }
        coverage = len(values)
        if coverage < min_symbols:
            continue
        advancing = sum(value > 0 for value in values.values())
        declining = sum(value < 0 for value in values.values())
        unchanged = coverage - advancing - declining
        breadth.append({
            "timestamp": timestamp,
            "symbols_observed": coverage,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_pct": round(100 * advancing / coverage, 2),
            "decline_pct": round(100 * declining / coverage, 2),
            "unchanged_pct": round(100 * unchanged / coverage, 2),
            "net_advances": advancing - declining,
        })

    latest = breadth[-1] if breadth else None
    return {
        "mode": "historical_descriptive_market_breadth",
        "symbols": sorted(returns_by_symbol),
        "minimum_symbols_per_timestamp": min_symbols,
        "observations": breadth,
        "latest_observation": latest,
        "alignment": "Exact timestamp matches only; unmatched observations are excluded and no interpolation is performed.",
        "limitations": [
            "Breadth reflects only symbols and stored observations supplied to this report.",
            "Different symbol universes, providers, and missing observations can change coverage and comparability.",
            "A positive or negative return is measured against each symbol's preceding stored close, not a provider calendar.",
            "This report is descriptive and does not forecast or recommend market direction.",
        ],
        "execution": "disabled",
    }
