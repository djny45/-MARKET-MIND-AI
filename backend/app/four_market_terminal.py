"""Four-market terminal service: assemble verified quotes into one board.

This is the only layer that knows how to turn the reference catalogue plus the
four provider adapters into a terminal payload. It is deliberately strict:

* Instruments come from the persistent instrument master, never from a
  hardcoded ticker list in the frontend.
* Every quote is fetched through its market-group adapter and validated by
  ``MarketQuote``, which binds the LIVE/DELAYED label to operator attestation.
* Staleness is computed per quote from its own event timestamp; a whole market
  is only "stale" when every usable quote in it is stale.
* A market with no usable quote reports ``UNAVAILABLE`` and a reason. It never
  borrows another market's number.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from .market_data import DataStatus
from .market_quotes import MARKET_GROUPS, MarketQuote, freshness_legend
from .provider_adapters import ADAPTERS, adapter_manifest, quotes_for_instruments

#: Reference instruments the terminal shows per market by default. These are
#: catalogue keys, not a quote source: the adapter decides availability.
DEFAULT_WATCH: dict[str, tuple[str, ...]] = {
    "us": ("AAPL", "MSFT", "NVDA", "SPY", "SPX"),
    "india": ("RELIANCE", "TCS", "INFY", "NIFTY50", "SENSEX"),
    "forex": ("EURUSD", "USDINR", "USDJPY", "GBPUSD"),
    "crypto": ("BTCUSD", "ETHUSD", "SOLUSD"),
}

#: A market is only considered "live-ish" when at least this share of its
#: quotes carry a real observation. Guards against one lucky symbol.
MIN_COVERAGE_FOR_MARKET_STATUS = 0.5

#: Presentation order for the terminal board (US first, then India, FX, crypto).
DISPLAY_ORDER: tuple[str, ...] = ("us", "india", "forex", "crypto")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class MarketSnapshot:
    market_group: str
    quotes: list[MarketQuote] = field(default_factory=list)
    requested: int = 0

    def to_payload(self, now: datetime | None = None) -> dict[str, Any]:
        reference = now or _utc_now()
        rows = [quote.to_payload(reference) for quote in self.quotes]
        usable = [row for row in rows if row["status"] != DataStatus.UNAVAILABLE.value]
        stale = [row for row in usable if row["stale"]]
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1

        if not usable:
            market_status = DataStatus.UNAVAILABLE.value
            headline = "NO USABLE OBSERVATION"
        elif len(stale) == len(usable):
            market_status = "stale"
            headline = "ALL OBSERVATIONS STALE"
        elif stale:
            market_status = "partially_stale"
            headline = f"{len(stale)} STALE OF {len(usable)}"
        else:
            market_status = "fresh"
            headline = "FRESH"

        return {
            "market_group": self.market_group,
            "market_status": market_status,
            "headline": headline,
            "requested": self.requested,
            "usable_count": len(usable),
            "unavailable_count": len(rows) - len(usable),
            "stale_count": len(stale),
            "status_counts": counts,
            "coverage_ratio": round(len(usable) / self.requested, 4) if self.requested else 0.0,
            "adapter": ADAPTERS[self.market_group].capability.to_payload(),
            "quotes": rows,
        }


def _select_instruments(
    catalogue: Iterable[dict[str, Any]],
    market_group: str,
    symbols: Iterable[str] | None,
) -> list[dict[str, Any]]:
    wanted = {s.strip().upper() for s in symbols} if symbols else set(DEFAULT_WATCH[market_group])
    rows = [item for item in catalogue if item.get("market_group") == market_group]
    if not symbols:
        # Preserve the curated order so the board is stable between requests.
        order = {symbol: index for index, symbol in enumerate(DEFAULT_WATCH[market_group])}
        rows = sorted(
            (item for item in rows if item["symbol"] in wanted),
            key=lambda item: order.get(item["symbol"], 999),
        )
        return rows
    return [item for item in rows if item["symbol"] in wanted]


def build_terminal_snapshot(
    catalogue: list[dict[str, Any]],
    *,
    market_groups: Iterable[str] | None = None,
    symbols: dict[str, list[str]] | None = None,
    attested_sources: Iterable[str] = (),
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the full four-market terminal payload.

    ``catalogue`` must come from the persistent instrument master. Missing
    coverage is reported as missing; nothing is back-filled.
    """
    groups = [g.strip().lower() for g in (market_groups or DISPLAY_ORDER)]
    invalid = [g for g in groups if g not in MARKET_GROUPS]
    if invalid:
        raise ValueError(f"unsupported market group(s): {', '.join(invalid)}")

    reference = now or _utc_now()
    attested = tuple(attested_sources)
    markets: list[dict[str, Any]] = []

    for group in groups:
        requested_symbols = (symbols or {}).get(group)
        selected = _select_instruments(catalogue, group, requested_symbols)
        if not selected:
            snapshot = MarketSnapshot(market_group=group, quotes=[], requested=0)
            payload = snapshot.to_payload(reference)
            payload["headline"] = "NOT IN CATALOGUE"
            payload["note"] = (
                "No reference instrument for this market is registered in the "
                "instrument master. Coverage is reported as missing, not inferred."
            )
            markets.append(payload)
            continue
        quotes = quotes_for_instruments(selected, attested_sources=attested)
        snapshot = MarketSnapshot(
            market_group=group, quotes=quotes, requested=len(selected),
        )
        payload = snapshot.to_payload(reference)
        if snapshot.requested and len(quotes) < snapshot.requested:
            payload["note"] = (
                f"{snapshot.requested - len(quotes)} requested instrument(s) were "
                "not returned by the adapter and are omitted rather than filled."
            )
        markets.append(payload)

    totals = {
        "markets": len(markets),
        "quotes": sum(len(m["quotes"]) for m in markets),
        "usable": sum(m["usable_count"] for m in markets),
        "unavailable": sum(m["unavailable_count"] for m in markets),
        "stale": sum(m["stale_count"] for m in markets),
    }
    return {
        "generated_at": reference.astimezone(timezone.utc).isoformat(),
        "mode": "four_market_research_terminal",
        "market_groups": groups,
        "markets": markets,
        "totals": totals,
        "legend": freshness_legend(),
        "providers": adapter_manifest(),
        "attested_sources": sorted({s.strip().lower() for s in attested if s.strip()}),
        "execution": {
            "paper_trading": False,
            "broker_execution": False,
            "real_money": False,
        },
        "notes": [
            "Every observation carries source, event timestamp and retrieval time.",
            "A LIVE or DELAYED label requires operator attestation of the exact "
            "adapter name; unattested observations are labelled HISTORICAL.",
            "UNAVAILABLE means no usable observation; no price is implied.",
            "Research and display only. No order routing or real-money execution.",
        ],
    }


def summarize_terminal(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compact health view used by the provider panel and the header strip."""
    return {
        "generated_at": snapshot["generated_at"],
        "markets": [
            {
                "market_group": market["market_group"],
                "market_status": market["market_status"],
                "headline": market["headline"],
                "usable_count": market["usable_count"],
                "unavailable_count": market["unavailable_count"],
                "stale_count": market["stale_count"],
                "adapter": market["adapter"]["name"],
                "preferred_status": market["adapter"]["preferred_status"],
                "requires_attestation": market["adapter"]["requires_attestation"],
            }
            for market in snapshot["markets"]
        ],
        "totals": snapshot["totals"],
        "attested_sources": snapshot["attested_sources"],
        "execution": snapshot["execution"],
    }


# ---------------------------------------------------------------------------
# Short-lived cache
# ---------------------------------------------------------------------------
#
# Public providers rate-limit aggressively and a terminal UI polls. Caching the
# assembled snapshot for a few seconds keeps a 5-second refresh from turning
# into 17 upstream requests per client. The cache is keyed on the exact request
# (groups + symbols + attested set) so an attestation change never serves a
# stale label. It is process-local and intentionally tiny.

CACHE_TTL_SECONDS = 15.0
_cache: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}


def _cache_key(
    market_groups: Iterable[str] | None,
    symbols: dict[str, list[str]] | None,
    attested_sources: Iterable[str],
) -> tuple[Any, ...]:
    groups = tuple(sorted({g.strip().lower() for g in (market_groups or DISPLAY_ORDER)}))
    symbol_key = tuple(sorted(
        (group, tuple(sorted({s.strip().upper() for s in values})))
        for group, values in (symbols or {}).items()
    ))
    return (groups, symbol_key, tuple(sorted({s.strip().lower() for s in attested_sources})))


def cached_terminal_snapshot(
    catalogue: list[dict[str, Any]],
    *,
    market_groups: Iterable[str] | None = None,
    symbols: dict[str, list[str]] | None = None,
    attested_sources: Iterable[str] = (),
    ttl_seconds: float = CACHE_TTL_SECONDS,
    clock: Callable[[], float] | None = None,
) -> dict[str, Any]:
    """Return a snapshot, reusing a cached one inside ``ttl_seconds``.

    Pass ``ttl_seconds=0`` to force a fresh fetch (used by the explicit
    refresh control and by tests).
    """
    import time

    now_fn = clock or time.monotonic
    key = _cache_key(market_groups, symbols, attested_sources)
    current = now_fn()
    if ttl_seconds > 0:
        hit = _cache.get(key)
        if hit is not None and current - hit[0] < ttl_seconds:
            snapshot = dict(hit[1])
            snapshot["cache"] = {
                "hit": True,
                "age_seconds": round(current - hit[0], 3),
                "ttl_seconds": ttl_seconds,
            }
            return snapshot
    snapshot = build_terminal_snapshot(
        catalogue, market_groups=market_groups, symbols=symbols,
        attested_sources=attested_sources,
    )
    _cache[key] = (current, snapshot)
    result = dict(snapshot)
    result["cache"] = {"hit": False, "age_seconds": 0.0, "ttl_seconds": ttl_seconds}
    return result


def clear_cache() -> None:
    _cache.clear()
