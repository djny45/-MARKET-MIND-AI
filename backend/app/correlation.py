"""Timestamp-aligned descriptive Pearson correlations for stored close series."""


def build_correlation_report(histories: dict[str, dict], min_observations: int = 3) -> dict:
    if min_observations < 3:
        raise ValueError("min_observations must be at least 3")
    if len(histories) < 2:
        raise ValueError("at least two symbols are required")
    aligned = {}
    for symbol, history in histories.items():
        points = {}
        for bar in history.get("bars", []):
            timestamp = bar.get("timestamp")
            try:
                close = float(bar["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if timestamp and close > 0:
                points[timestamp] = close
        aligned[symbol.upper()] = points

    symbols = sorted(aligned)
    returns = {}
    for symbol in symbols:
        points = aligned[symbol]
        ordered = sorted(points.items())
        returns[symbol] = {
            ordered[i][0]: ordered[i][1] / ordered[i - 1][1] - 1
            for i in range(1, len(ordered))
            if ordered[i - 1][1] > 0
        }

    matrix, observations = {}, {}
    for left in symbols:
        matrix[left], observations[left] = {}, {}
        for right in symbols:
            common = sorted(set(returns[left]) & set(returns[right]))
            observations[left][right] = len(common)
            if len(common) < min_observations:
                matrix[left][right] = None
                continue
            xs = [returns[left][key] for key in common]
            ys = [returns[right][key] for key in common]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            dx = sum((x - mx) ** 2 for x in xs)
            dy = sum((y - my) ** 2 for y in ys)
            if dx == 0 or dy == 0:
                matrix[left][right] = None
            else:
                covariance = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
                matrix[left][right] = round(covariance / (dx * dy) ** 0.5, 6)

    return {
        "mode": "historical_descriptive_correlation",
        "symbols": symbols,
        "pearson_return_correlation": matrix,
        "paired_return_observations": observations,
        "minimum_observations": min_observations,
        "alignment": "Exact timestamp matches only; unmatched observations are excluded.",
        "limitations": [
            "Correlation describes historical co-movement and does not establish causation.",
            "Correlation can change across samples and market regimes.",
            "Insufficient or constant return series are represented as null.",
            "This report does not forecast or recommend portfolio allocations.",
        ],
        "execution": "disabled",
    }
