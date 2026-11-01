"""OHLCV-derived liquidity profile diagnostics for historical research.

Volume-at-price is estimated from each bar's typical price. It is not a true
trade-level volume profile and does not represent order-book liquidity.
"""
from math import isfinite


def _validate(high, low, close, volume):
    columns = {"high": high, "low": low, "close": close, "volume": volume}
    lengths = {len(values) for values in columns.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 2:
        raise ValueError("OHLCV arrays must have equal lengths of at least two")
    clean = {}
    for name, values in columns.items():
        try:
            clean[name] = [float(value) for value in values]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} values must be numeric") from exc
        if any(not isfinite(value) for value in clean[name]):
            raise ValueError(f"{name} values must be finite")
    for i, (h, l, c, v) in enumerate(zip(clean["high"], clean["low"], clean["close"], clean["volume"])):
        if l <= 0 or h < l or not l <= c <= h:
            raise ValueError(f"invalid OHLC values at index {i}")
        if v < 0:
            raise ValueError(f"volume cannot be negative at index {i}")
    return clean


def calculate_volume_profile(high, low, close, volume, bins=48, value_area_pct=70.0):
    """Return approximate volume-at-price bins, POC, value area and nodes.

    Each candle's entire volume is assigned to its typical price. This is a
    transparent OHLCV proxy; trade-level data is required for true VAP.
    """
    if isinstance(bins, bool) or not isinstance(bins, int) or not 2 <= bins <= 500:
        raise ValueError("bins must be an integer between 2 and 500")
    if not isinstance(value_area_pct, (int, float)) or not isfinite(value_area_pct) or not 1 <= value_area_pct <= 100:
        raise ValueError("value_area_pct must be between 1 and 100")
    x = _validate(high, low, close, volume)
    typical = [(h + l + c) / 3 for h, l, c in zip(x["high"], x["low"], x["close"])]
    min_price, max_price = min(typical), max(typical)
    if max_price == min_price:
        edges = [min_price, max_price]
        profile = [{"price_low": min_price, "price_high": max_price, "price_mid": min_price,
                    "volume": sum(x["volume"]), "share_pct": 100.0 if sum(x["volume"]) else 0.0}]
    else:
        width = (max_price - min_price) / bins
        volumes = [0.0] * bins
        for price, amount in zip(typical, x["volume"]):
            index = min(bins - 1, int((price - min_price) / width))
            volumes[index] += amount
        edges = [min_price + i * width for i in range(bins + 1)]
        total = sum(volumes)
        profile = [{
            "price_low": edges[i], "price_high": edges[i + 1],
            "price_mid": (edges[i] + edges[i + 1]) / 2,
            "volume": volumes[i], "share_pct": volumes[i] / total * 100 if total else 0.0,
        } for i in range(bins)]
    total = sum(item["volume"] for item in profile)
    poc_index = max(range(len(profile)), key=lambda i: profile[i]["volume"])
    left = right = poc_index
    accumulated = profile[poc_index]["volume"]
    target = total * value_area_pct / 100
    while accumulated < target and (left > 0 or right < len(profile) - 1):
        left_volume = profile[left - 1]["volume"] if left > 0 else -1
        right_volume = profile[right + 1]["volume"] if right < len(profile) - 1 else -1
        if right_volume > left_volume:
            right += 1
            accumulated += profile[right]["volume"]
        else:
            left -= 1
            accumulated += profile[left]["volume"]
    nodes = []
    for i, item in enumerate(profile):
        previous = profile[i - 1]["volume"] if i else -1
        following = profile[i + 1]["volume"] if i < len(profile) - 1 else -1
        if item["volume"] > 0 and item["volume"] >= previous and item["volume"] >= following:
            nodes.append({"type": "local_high_volume_node", "price": item["price_mid"], "volume": item["volume"]})
        if item["volume"] > 0 and item["volume"] <= previous and item["volume"] <= following:
            nodes.append({"type": "local_low_volume_node", "price": item["price_mid"], "volume": item["volume"]})
    return {
        "profile": profile,
        "poc": profile[poc_index]["price_mid"] if total else None,
        "value_area_high": profile[right]["price_high"] if total else None,
        "value_area_low": profile[left]["price_low"] if total else None,
        "value_area_pct_requested": float(value_area_pct),
        "value_area_volume_pct_actual": accumulated / total * 100 if total else 0.0,
        "total_volume": total,
        "nodes": nodes,
        "metadata": {
            "method": "typical_price_per_bar_volume_assignment",
            "classification": "ohlcv_approximation_not_trade_level_volume_at_price",
            "bars": len(typical), "bins": len(profile),
            "purpose": "historical_descriptive_research_only",
        },
    }
