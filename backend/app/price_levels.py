"""Descriptive clusters of confirmed historical swing-price observations."""
from .swing_points import find_swing_points


def build_price_level_clusters(
    bars: list[dict], tolerance_pct: float = 0.5, min_touches: int = 2,
    left: int = 2, right: int = 2,
) -> dict:
    if tolerance_pct <= 0 or tolerance_pct > 10:
        raise ValueError("tolerance_pct must be greater than 0 and at most 10")
    if min_touches < 2:
        raise ValueError("min_touches must be at least 2")
    pivots = find_swing_points(bars, left=left, right=right)
    result = {}
    for side, key in (("historical_swing_high", "confirmed_swing_highs"),
                      ("historical_swing_low", "confirmed_swing_lows")):
        points = sorted(pivots[key], key=lambda item: item["price"])
        clusters = []
        for point in points:
            if not clusters:
                clusters.append([point])
                continue
            center = sum(item["price"] for item in clusters[-1]) / len(clusters[-1])
            if abs(point["price"] - center) / center * 100 <= tolerance_pct:
                clusters[-1].append(point)
            else:
                clusters.append([point])
        result[side] = [
            {
                "mean_price": round(sum(item["price"] for item in cluster) / len(cluster), 8),
                "lower_price": min(item["price"] for item in cluster),
                "upper_price": max(item["price"] for item in cluster),
                "touch_count": len(cluster),
                "pivot_timestamps": [item.get("timestamp") for item in cluster],
                "pivot_indices": [item["index"] for item in cluster],
            }
            for cluster in clusters if len(cluster) >= min_touches
        ]
    return {
        "status": "calculated",
        "tolerance_pct": tolerance_pct,
        "minimum_touches": min_touches,
        "left_confirmation_bars": left,
        "right_confirmation_bars": right,
        "clusters": result,
        "interpretation": "Historical concentrations of confirmed swing prices only; not guaranteed support, resistance, targets or forecasts.",
        "limitations": [
            "Clusters depend on the selected tolerance and swing confirmation windows.",
            "Only confirmed pivots are included; the most recent unconfirmed extrema are excluded.",
            "A cluster is a descriptive price concentration, not evidence of future price reaction.",
        ],
    }
