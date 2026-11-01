"""Descriptive aggregation of imported historical trade events only."""
from datetime import datetime, timezone
import math

def _epoch(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).timestamp()

def build_trade_flow_buckets(events, bucket_seconds=60, total_matching=None, limit=None):
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
