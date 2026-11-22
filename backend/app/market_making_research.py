"""Compatibility exports for the canonical AutoHedge-inspired research module.

Keep this path temporarily for older internal imports. All calculations are
delegated to the canonical implementation so assumptions do not drift.
"""
from datetime import datetime, timezone

from .autohedge_market_making_research import (
    BookSnapshot,
    MarketMakingResearchConfig,
    calculate_research_quotes,
)


def calculate_market_making_research(
    snapshot,
    *,
    observed_at=None,
    max_age_seconds=30,
    half_spread_bps=10,
    inventory=0,
    inventory_skew_bps=0,
):
    """Compatibility adapter; output remains indicative and research-only."""
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot must be a mapping")
    try:
        timestamp = datetime.fromisoformat(str(snapshot.get("timestamp")).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("timestamp must be ISO-8601") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    book = BookSnapshot(
        bid=float(snapshot.get("best_bid")),
        ask=float(snapshot.get("best_ask")),
        timestamp=timestamp.timestamp(),
    )
    skew_per_unit = float(inventory_skew_bps)
    config = MarketMakingResearchConfig(
        half_spread_bps=float(half_spread_bps),
        max_data_age_seconds=float(max_age_seconds),
        inventory_skew_bps_per_unit=skew_per_unit,
    )
    result = calculate_research_quotes(
        book, config, now=now.timestamp(), inventory_units=float(inventory)
    )
    return {
        "mode": "research_only_indicative",
        "timestamp": timestamp.isoformat(),
        "age_seconds": (now - timestamp).total_seconds(),
        "best_bid": str(book.bid),
        "best_ask": str(book.ask),
        "mid": str(result["mid_price"]),
        "spread": str(book.ask - book.bid),
        "spread_bps": str((book.ask - book.bid) / result["mid_price"] * 10000),
        "indicative_bid": str(result["indicative_bid"]),
        "indicative_ask": str(result["indicative_ask"]),
        "inventory": str(inventory),
        "inventory_skew_bps": str(inventory_skew_bps),
        "limitations": [
            "No venue connection, order construction, placement, cancellation, wallet, signing or live execution.",
            "Does not model queue position, adverse selection, latency, depth or partial fills.",
        ],
    }
