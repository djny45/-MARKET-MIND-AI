"""Pure market-making research calculations over supplied order-book snapshots."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def _number(value, label):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"{label} must be a finite positive number") from exc
    if not result.is_finite() or result <= 0:
        raise ValueError(f"{label} must be a finite positive number")
    return result


def calculate_market_making_research(snapshot, *, observed_at=None, max_age_seconds=30,
                                     half_spread_bps=10, inventory=0, inventory_skew_bps=0):
    """Return indicative prices only; never constructs venue/order API requests."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a mapping")
    bid = _number(snapshot.get("best_bid"), "best_bid")
    ask = _number(snapshot.get("best_ask"), "best_ask")
    stamp = snapshot.get("timestamp")
    try:
        timestamp = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    age = (now - timestamp).total_seconds()
    if age < 0:
        raise ValueError("future-dated order book is not accepted")
    if age > max_age_seconds:
        raise ValueError("stale order book is not accepted")
    if bid >= ask:
        raise ValueError("crossed or locked order book is not accepted")
    spread_bps = (ask - bid) / ((ask + bid) / Decimal("2")) * Decimal("10000")
    half = _number(half_spread_bps, "half_spread_bps") / Decimal("10000")
    try:
        inventory_value = Decimal(str(inventory))
        skew_bps = Decimal(str(inventory_skew_bps))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("inventory inputs must be finite decimals") from exc
    if not inventory_value.is_finite() or not skew_bps.is_finite() or skew_bps < 0:
        raise ValueError("inventory inputs must be finite and skew must be non-negative")
    mid = (bid + ask) / Decimal("2")
    skew = inventory_value * skew_bps / Decimal("10000")
    # Positive inventory moves indicative center down; negative inventory moves it up.
    center = mid * (Decimal("1") - skew)
    bid_quote = center * (Decimal("1") - half)
    ask_quote = center * (Decimal("1") + half)
    if bid_quote <= 0 or ask_quote <= bid_quote:
        raise ValueError("inventory skew produces invalid indicative quotes")
    return {
        "mode": "research_only_indicative",
        "timestamp": timestamp.isoformat(),
        "age_seconds": age,
        "best_bid": str(bid), "best_ask": str(ask),
        "mid": str(mid), "spread": str(ask - bid),
        "spread_bps": str(spread_bps),
        "indicative_bid": str(bid_quote), "indicative_ask": str(ask_quote),
        "inventory": str(inventory_value), "inventory_skew_bps": str(skew_bps),
        "limitations": ["No venue connection, order construction, placement, cancellation, wallet, signing or live execution.",
                        "Does not model queue position, adverse selection, latency, depth or partial fills."]
    }
