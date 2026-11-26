"""Historical microstructure event quality diagnostics; never emits trading signals."""
from collections import defaultdict
from datetime import datetime


def _instant(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return None
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def diagnose_market_events(events):
    """Inspect a supplied event collection; does not repair, reorder or infer events."""
    groups = defaultdict(list)
    invalid_timestamps, clock_anomalies = [], []
    snapshot_anomalies = []
    for index, event in enumerate(events):
        event_time = _instant(event.get("event_time"))
        received_time = _instant(event.get("received_at"))
        if event_time is None:
            invalid_timestamps.append({"event_index": index, "field": "event_time"})
        if received_time is None:
            invalid_timestamps.append({"event_index": index, "field": "received_at"})
        if event_time is not None and received_time is not None:
            lag = received_time - event_time
            if lag < 0:
                clock_anomalies.append({"event_index": index, "lag_seconds": round(lag, 6),
                                        "kind": "received_before_event"})
        key = (event.get("provider"), event.get("venue"), event.get("instrument_id"), event.get("event_type"))
        if event.get("sequence_number") is not None:
            groups[key].append((event["sequence_number"], index, event.get("event_id"), event_time))
        if event.get("event_type") == "order_book_snapshot":
            payload = event.get("payload") or {}
            bids, asks = payload.get("bids") or [], payload.get("asks") or []
            bid_prices = [float(level["price"]) for level in bids if isinstance(level, dict) and "price" in level]
            ask_prices = [float(level["price"]) for level in asks if isinstance(level, dict) and "price" in level]
            problems = []
            if len(bid_prices) != len(bids) or len(ask_prices) != len(asks):
                problems.append("invalid_level_shape")
            if any(a < b for a, b in zip(bid_prices, bid_prices[1:])):
                problems.append("bids_not_descending")
            if any(a > b for a, b in zip(ask_prices, ask_prices[1:])):
                problems.append("asks_not_ascending")
            if bid_prices and ask_prices and max(bid_prices) >= min(ask_prices):
                problems.append("crossed_or_locked_snapshot")
            if problems:
                snapshot_anomalies.append({"event_index": index, "event_id": event.get("event_id"),
                                           "issues": problems})
    sequence_gaps, duplicate_sequences, out_of_order = [], [], []
    for key, records in groups.items():
        ordered = sorted(records, key=lambda item: (item[3] if item[3] is not None else float("inf"), item[0]))
        seen = {}
        for sequence, index, event_id, _event_time in ordered:
            if sequence in seen:
                duplicate_sequences.append({"scope": list(key), "sequence_number": sequence,
                                            "first_event_index": seen[sequence], "event_index": index,
                                            "event_id": event_id})
            else:
                seen[sequence] = index
        for (prev_seq, prev_idx, _, _), (seq, idx, event_id, _event_time) in zip(ordered, ordered[1:]):
            if seq < prev_seq:
                out_of_order.append({"scope": list(key), "previous_sequence": prev_seq,
                                     "sequence_number": seq, "event_index": idx, "event_id": event_id})
            elif seq > prev_seq + 1:
                sequence_gaps.append({"scope": list(key), "from_sequence": prev_seq,
                                      "to_sequence": seq, "missing_sequence_count": seq - prev_seq - 1,
                                      "event_index": idx})
    return {
        "events_checked": len(events),
        "sequence_integrity": {
            "groups_checked": len(groups), "gap_count": len(sequence_gaps), "gaps": sequence_gaps,
            "duplicate_sequence_count": len(duplicate_sequences), "duplicates": duplicate_sequences,
            "out_of_order_count": len(out_of_order), "out_of_order": out_of_order,
            "interpretation": "Sequence checks apply only within provider, venue, instrument and event type; gaps may reflect partial imports or provider semantics."
        },
        "timestamp_integrity": {
            "invalid_timestamp_count": len(invalid_timestamps), "invalid_timestamps": invalid_timestamps,
            "received_before_event_count": len(clock_anomalies), "clock_anomalies": clock_anomalies,
            "interpretation": "Negative receive lag may indicate clock skew or inconsistent source timestamps; no timestamp is corrected."
        },
        "order_book_integrity": {
            "anomaly_count": len(snapshot_anomalies), "anomalies": snapshot_anomalies,
            "interpretation": "Checks require bids sorted descending and asks ascending; locked/crossed snapshots are flagged for review, not repaired."
        },
        "methodology": [
            "Sequence numbers are compared in event-time order only within provider/venue/instrument/event-type groups; equal-time records are ordered by sequence number.",
            "A gap is not proof of data loss unless the provider guarantees contiguous sequence semantics.",
            "Diagnostics are review prompts, not data-authenticity proofs, execution inputs or trading signals.",
            "Only the queried event sample is inspected; pagination or a larger limit may be needed for full-history review."
        ]
    }


# EXTENSION: field and freshness diagnostics for microstructure events.
# These report anomalies only; they never repair, drop or synthesize records.

REQUIRED_EVENT_FIELDS = (
    "event_id", "instrument_id", "event_type", "provider", "venue",
    "event_time", "received_at", "status", "payload",
)

PAYLOAD_REQUIREMENTS = {
    "trade": ("price", "quantity"),
    "quote": ("bid_price", "ask_price"),
    "order_book_snapshot": ("bids", "asks"),
    "order_book_delta": ("previous_sequence_number", "bids", "asks"),
    "liquidation": ("price", "quantity", "side"),
    "open_interest": ("value", "unit"),
    "funding": ("rate", "interval", "settlement_currency"),
    "fx_rate": ("rate", "base", "quote", "rate_type"),
}

# Descriptive staleness thresholds in seconds, matching the quote contract.
EVENT_STALENESS_THRESHOLDS = {
    "live": 60, "delayed": 900, "end_of_day": 86400,
    "reference": 7 * 86400, "synthetic": 3600,
}


def diagnose_event_fields(events):
    """Report missing or malformed required fields without modifying records."""
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    missing, malformed, unknown_types = [], [], []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            malformed.append({"event_index": index, "reason": "not_an_object"})
            continue
        for field in REQUIRED_EVENT_FIELDS:
            if field not in event or event[field] in (None, ""):
                missing.append({"event_index": index, "field": field})
        payload = event.get("payload")
        if not isinstance(payload, dict):
            malformed.append({"event_index": index, "field": "payload", "reason": "not_an_object"})
            continue
        kind = event.get("event_type")
        if kind not in PAYLOAD_REQUIREMENTS:
            unknown_types.append({"event_index": index, "event_type": kind})
            continue
        for field in PAYLOAD_REQUIREMENTS[kind]:
            if field not in payload or payload[field] in (None, ""):
                missing.append({
                    "event_index": index, "field": f"payload.{field}",
                    "event_type": kind,
                })
    return {
        "events_inspected": len(events),
        "missing_field_count": len(missing),
        "malformed_count": len(malformed),
        "unknown_event_type_count": len(unknown_types),
        "missing_fields": missing[:200],
        "malformed": malformed[:200],
        "unknown_event_types": unknown_types[:200],
        "data_note": "Reports supplied fields only; no field is inferred or filled.",
    }


def diagnose_event_staleness(events, now=None):
    """Report events whose age exceeds the threshold for their status label."""
    if not isinstance(events, list):
        raise ValueError("events must be a list")
    reference = datetime.now(tz=now.tzinfo) if now and now.tzinfo else datetime.now()
    reference_epoch = reference.timestamp()
    stale, unlabelled, fresh = [], [], 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            continue
        status = str(event.get("status") or "").lower()
        threshold = EVENT_STALENESS_THRESHOLDS.get(status)
        if threshold is None:
            unlabelled.append({"event_index": index, "status": status or None})
            continue
        event_epoch = _instant(event.get("event_time"))
        if event_epoch is None:
            unlabelled.append({"event_index": index, "status": status, "reason": "invalid_event_time"})
            continue
        age = max(0, int(reference_epoch - event_epoch))
        if age > threshold:
            stale.append({
                "event_index": index, "status": status,
                "age_seconds": age, "max_age_seconds": threshold,
                "event_time": event.get("event_time"),
            })
        else:
            fresh += 1
    return {
        "events_inspected": len(events), "fresh_count": fresh,
        "stale_count": len(stale), "unlabelled_count": len(unlabelled),
        "stale": stale[:200], "unlabelled": unlabelled[:200],
        "data_note": (
            "Staleness is descriptive against the status threshold. It does "
            "not authenticate a provider or change the event status."
        ),
    }
