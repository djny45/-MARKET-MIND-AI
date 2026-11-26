"""Descriptive aggregation of imported historical trade events only."""
from datetime import datetime, timezone
import math

def _epoch(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).timestamp()

def build_market_flow_summary(events, *, large_trade_notional=None, limit=500):
    """Derive executed-trade flow metrics from existing market events.

    EXTENDS ``build_trade_flow_buckets`` without replacing it. Trade notional
    is derived only when the importer supplied both quantity and price; nothing
    is inferred from order books or from a reference rate. Large trades use a
    caller-supplied notional threshold, never an undocumented proprietary rule.
    """
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    if large_trade_notional is not None:
        try:
            threshold = float(large_trade_notional)
        except (TypeError, ValueError) as exc:
            raise ValueError("large_trade_notional must be a finite positive number") from exc
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError("large_trade_notional must be a finite positive number")
    else:
        threshold = None
    sampled = events[:max(1, min(int(limit), 5000))]
    classified = []
    unpriced = 0
    buy_notional = sell_notional = 0.0
    buy_count = sell_count = 0
    large = []
    for event in sampled:
        if event.get("event_type") != "trade":
            continue
        payload = event.get("payload") or {}
        side = payload.get("side")
        if side not in {"buy", "sell"}:
            continue
        quantity = _finite_positive(payload.get("quantity"))
        price = _finite_positive(payload.get("price"))
        if quantity is None or price is None:
            unpriced += 1
            continue
        notional = quantity * price
        row = {
            "event_id": event.get("event_id"),
            "event_time": event.get("event_time"),
            "side": side,
            "quantity": round(quantity, 10),
            "price": round(price, 10),
            "notional": round(notional, 6),
        }
        classified.append(row)
        if side == "buy":
            buy_notional += notional
            buy_count += 1
        else:
            sell_notional += notional
            sell_count += 1
        if threshold is not None and notional >= threshold:
            large.append({**row, "large": True, "threshold": threshold})
    total_notional = buy_notional + sell_notional
    by_notional = sorted(classified, key=lambda row: row["notional"], reverse=True)[:20]
    max_notional = by_notional[0]["notional"] if by_notional else 0.0
    for row in classified:
        # Relative size = this trade's notional vs the largest sampled trade.
        row["relative_size"] = round(row["notional"] / max_notional, 6) if max_notional else None
    for row in large:
        source_row = next(item for item in classified if item["event_id"] == row["event_id"])
        row["relative_size"] = source_row["relative_size"]
    delta = buy_notional - sell_notional
    return {
        "trade_events_sampled": len(sampled),
        "classified_trades": len(classified),
        "unpriced_trades_excluded": unpriced,
        "buy_count": buy_count, "sell_count": sell_count,
        "buy_notional": round(buy_notional, 6), "sell_notional": round(sell_notional, 6),
        "net_notional_delta": round(delta, 6),
        "buy_share": round(buy_notional / total_notional, 6) if total_notional else None,
        "flow_direction": (
            "buy_dominant" if delta > 0 else "sell_dominant" if delta < 0 else "balanced"
        ) if classified else "unavailable",
        "large_trade_threshold": threshold,
        "large_trades": large[:50],
        "largest_trades": by_notional,
        "trades": classified[:200],
        "data_note": (
            "Derived from supplied trade events only. Notional requires both "
            "quantity and price from the importer; missing values are excluded, "
            "never invented. Flow direction describes sampled executed trades "
            "and does not predict future prices. Relative size is normalized "
            "to the largest sampled trade."
        ),
    }


def build_liquidation_summary(events, *, limit=1000):
    """Summarize stored liquidation events from the existing event store."""
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    long_notional = short_notional = 0.0
    long_count = short_count = 0
    clusters = {}
    rows = []
    for event in events[:max(1, min(int(limit), 5000))]:
        if event.get("event_type") != "liquidation":
            continue
        payload = event.get("payload") or {}
        price = _finite_positive(payload.get("price"))
        quantity = _finite_positive(payload.get("quantity"))
        if price is None or quantity is None:
            continue
        notional = price * quantity
        side = payload.get("side")
        if side == "long":
            long_notional += notional
            long_count += 1
        elif side == "short":
            short_notional += notional
            short_count += 1
        bucket = round(price, -max(0, len(str(int(price))) - 2))
        clusters[str(bucket)] = clusters.get(str(bucket), 0) + notional
        rows.append({
            "event_id": event.get("event_id"),
            "event_time": event.get("event_time"),
            "venue": event.get("venue"),
            "provider": event.get("provider"),
            "side": side,
            "notional": round(notional, 6),
        })
    total = long_notional + short_notional
    return {
        "liquidation_events": len(rows),
        "long_count": long_count, "short_count": short_count,
        "long_notional": round(long_notional, 6),
        "short_notional": round(short_notional, 6),
        "net_liquidation_notional": round(long_notional - short_notional, 6),
        "largest_price_clusters": sorted(
            ({"price_level": level, "notional": round(value, 6)}
             for level, value in clusters.items()),
            key=lambda row: row["notional"], reverse=True,
        )[:10],
        "events": rows[:100],
        "data_note": (
            "Summarizes stored liquidation events only. Exchange attribution "
            "comes from each event's provider/venue. No liquidation is inferred "
            "from price movement or order-book data."
        ),
    }


def _finite_positive(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def build_visual_trade_dots(events, *, limit=200):
    """Original dot payload for the existing chart: size=notional, colour=side.

    This is data preparation, not a chart engine. The existing ``PriceChart``
    renders the markers; no Tredye source, asset or algorithm is copied.
    """
    summary = build_market_flow_summary(events, limit=limit)
    dots = []
    for row in summary["trades"]:
        dots.append({
            "time": row["event_time"],
            "side": row["side"],
            "size": row["relative_size"],
            "notional": row["notional"],
            "colour": "#62b58e" if row["side"] == "buy" else "#d77970",
        })
    for row in summary["large_trades"]:
        dots.append({
            "time": row["event_time"], "side": "liquidation_marker",
            "size": row["relative_size"], "notional": row["notional"],
            "colour": "#d6a34e",
        })
    return {
        "dots": dots,
        "count": len(dots),
        "data_note": (
            "Dot size is relative notional; green=buy, red=sell, amber=large "
            "trade marker. These are executed-trade observations, not resting "
            "order-book orders."
        ),
    }

    if not isinstance(bucket_seconds, int) or isinstance(bucket_seconds, bool) or not 1 <= bucket_seconds <= 86400:
        raise ValueError("bucket_seconds must be between 1 and 86400")
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    buckets = {}
    for event in events:
        if event.get("event_type") != "trade":
            continue
        payload = event.get("payload") or {}
        quantity = float(payload.get("quantity"))
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("trade quantity must be finite and positive")
        side = payload.get("side", "unknown")
        if side not in {"buy", "sell", "unknown"}:
            side = "unknown"
        start_epoch = math.floor(_epoch(event["event_time"]) / bucket_seconds) * bucket_seconds
        bucket = buckets.setdefault(start_epoch, {
            "trade_count": 0, "total_volume": 0.0, "buy_volume": 0.0,
            "sell_volume": 0.0, "unknown_volume": 0.0,
        })
        bucket["trade_count"] += 1
        bucket["total_volume"] += quantity
        bucket[f"{side}_volume"] += quantity

    ordered = []
    cumulative = 0.0
    all_classified = all(bucket["unknown_volume"] == 0 for bucket in buckets.values())
    for start_epoch, bucket in sorted(buckets.items()):
        known_volume = bucket["buy_volume"] + bucket["sell_volume"]
        delta = bucket["buy_volume"] - bucket["sell_volume"]
        coverage = known_volume / bucket["total_volume"] if bucket["total_volume"] else 0.0
        if all_classified:
            cumulative += delta
        ordered.append({
            "bucket_start": datetime.fromtimestamp(start_epoch, timezone.utc).isoformat(),
            **{key: round(value, 10) for key, value in bucket.items()},
            "known_side_volume": round(known_volume, 10),
            "side_classification_coverage": round(coverage, 6),
            "known_side_delta": round(delta, 10),
            "cumulative_volume_delta": round(cumulative, 10) if all_classified else None,
            "cvd_status": "complete" if all_classified else "unavailable_incomplete_side_classification",
        })

    sampled = len(events)
    matched = sampled if total_matching is None else total_matching
    truncated = limit is not None and matched > sampled
    return {
        "bucket_seconds": bucket_seconds,
        "bucket_count": len(ordered),
        "trade_events_sampled": sampled,
        "trade_events_matching": matched,
        "truncated": truncated,
        "buckets": ordered,
        "side_classification": "complete" if all_classified else "partial_or_unknown",
        "cvd_available": all_classified and bool(ordered),
        "data_note": "Aggregates imported historical trade events only. Buy/sell side semantics are supplied by the importer; unknown side volume is never imputed. CVD is withheld for the sample if any trade has unknown side.",
    }


def build_trade_flow_buckets(events, bucket_seconds=60, total_matching=None, limit=None):
    """Time-bucketed buy/sell volume and CVD from imported trade events only."""
    if not isinstance(bucket_seconds, int) or isinstance(bucket_seconds, bool) or not 1 <= bucket_seconds <= 86400:
        raise ValueError("bucket_seconds must be between 1 and 86400")
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    buckets = {}
    for event in events:
        if event.get("event_type") != "trade":
            continue
        payload = event.get("payload") or {}
        quantity = float(payload.get("quantity"))
        if not math.isfinite(quantity) or quantity <= 0:
            raise ValueError("trade quantity must be finite and positive")
        side = payload.get("side", "unknown")
        if side not in {"buy", "sell", "unknown"}:
            side = "unknown"
        start_epoch = math.floor(_epoch(event["event_time"]) / bucket_seconds) * bucket_seconds
        bucket = buckets.setdefault(start_epoch, {
            "trade_count": 0, "total_volume": 0.0, "buy_volume": 0.0,
            "sell_volume": 0.0, "unknown_volume": 0.0,
        })
        bucket["trade_count"] += 1
        bucket["total_volume"] += quantity
        bucket[f"{side}_volume"] += quantity

    ordered = []
    cumulative = 0.0
    all_classified = all(bucket["unknown_volume"] == 0 for bucket in buckets.values())
    for start_epoch, bucket in sorted(buckets.items()):
        known_volume = bucket["buy_volume"] + bucket["sell_volume"]
        delta = bucket["buy_volume"] - bucket["sell_volume"]
        coverage = known_volume / bucket["total_volume"] if bucket["total_volume"] else 0.0
        if all_classified:
            cumulative += delta
        ordered.append({
            "bucket_start": datetime.fromtimestamp(start_epoch, timezone.utc).isoformat(),
            **{key: round(value, 10) for key, value in bucket.items()},
            "known_side_volume": round(known_volume, 10),
            "side_classification_coverage": round(coverage, 6),
            "known_side_delta": round(delta, 10),
            "cumulative_volume_delta": round(cumulative, 10) if all_classified else None,
            "cvd_status": "complete" if all_classified else "unavailable_incomplete_side_classification",
        })

    sampled = len(events)
    matched = sampled if total_matching is None else total_matching
    truncated = limit is not None and matched > sampled
    return {
        "bucket_seconds": bucket_seconds,
        "bucket_count": len(ordered),
        "trade_events_sampled": sampled,
        "trade_events_matching": matched,
        "truncated": truncated,
        "buckets": ordered,
        "side_classification": "complete" if all_classified else "partial_or_unknown",
        "cvd_available": all_classified and bool(ordered),
        "data_note": "Aggregates imported historical trade events only. Buy/sell side semantics are supplied by the importer; unknown side volume is never imputed. CVD is withheld for the sample if any trade has unknown side.",
    }
