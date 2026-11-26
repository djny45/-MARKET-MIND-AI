"""Public exchange/reference adapters for order-flow research.

This module EXTENDS the existing architecture — it does not create a parallel
provider system:

* Every adapter returns the existing ``MarketQuote`` / ``MarketDataBatch``
  contracts from ``market_data.py`` and ``market_quotes.py``.
* Every HTTP request goes through the existing ``provider_policy.LIMITER``
  (pacing, cache, Retry-After, bounded backoff). No limit bypass.
* Every source must pass the existing ``data_licensing_gate`` before it can be
  labelled LIVE or DELAYED. No source here is attested, so all observations are
  HISTORICAL. Failed or unverifiable responses become UNAVAILABLE with a
  reason; no price is fabricated.
* Only official, public, unauthenticated endpoints are used. Tredye's observed
  third-party endpoints are deliberately NOT called.

Gold is supplied as PAX Gold (a tokenized, exchange-traded instrument) via the
same public CoinGecko endpoint. It is NOT presented as spot gold or a futures
contract. Coinbase USD/INR is explicitly a reference rate, never executable FX.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from .market_data import DataStatus
from .market_quotes import MarketQuote, unavailable_quote
from .provider_adapters import ProviderCapability, ProviderError, USER_AGENT

CAPABILITIES: dict[str, ProviderCapability] = {
    "okx-public": ProviderCapability(
        name="okx-public", market_group="crypto",
        asset_classes=("spot", "perpetual", "options"),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="Official OKX public V5 REST endpoints; rate limits and terms apply.",
        limitations=("Public REST snapshot; not a full order-book stream.",),
    ),
    "coinbase-public": ProviderCapability(
        name="coinbase-public", market_group="crypto",
        asset_classes=("spot", "reference_rate"),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="Official Coinbase public endpoints; reference rates are informational.",
        limitations=("A USD/INR reference rate is not an executable forex quote.",),
    ),
    "bybit-public": ProviderCapability(
        name="bybit-public", market_group="crypto",
        asset_classes=("spot", "derivatives"),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="Official Bybit public V5 endpoints; terms and rate limits apply.",
        limitations=("Public snapshot; liquidation feeds may require a licensed stream.",),
    ),
    "kraken-public": ProviderCapability(
        name="kraken-public", market_group="crypto",
        asset_classes=("spot",),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="Official Kraken public endpoints; terms and rate limits apply.",
        limitations=("Public snapshot; no liquidation stream in the public REST API.",),
    ),
    "deribit-public": ProviderCapability(
        name="deribit-public", market_group="crypto",
        asset_classes=("options", "index"),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="Official Deribit public API; options data terms apply.",
        limitations=("Index price only unless an options chain is separately attested.",),
    ),
    "hyperliquid-public": ProviderCapability(
        name="hyperliquid-public", market_group="crypto",
        asset_classes=("spot", "perpetual"),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="Official Hyperliquid public info endpoint.",
        limitations=("Public information only; no authenticated account data.",),
    ),
    "alternative-sentiment": ProviderCapability(
        name="alternative-sentiment", market_group="crypto",
        asset_classes=("sentiment",),
        native_granularity="daily",
        preferred_status=DataStatus.HISTORICAL, requires_attestation=False,
        licensing_note="Alternative.me public Fear & Greed Index; attribution required.",
        limitations=("Daily sentiment indicator; not a price or trading signal.",),
    ),
    "coingecko-gold-token": ProviderCapability(
        name="coingecko-gold-token", market_group="crypto",
        asset_classes=("tokenized_gold",),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED, requires_attestation=True,
        licensing_note="PAX Gold via CoinGecko public API; tokenized gold, not spot or futures.",
        limitations=("An exchange-traded token, not interchangeable with spot/futures gold.",),
    ),
}

_ENDPOINTS: dict[str, tuple[str, str]] = {
    # (path, query)
    "okx_ticker": ("https://www.okx.com/api/v5/market/ticker", {"instId": "BTC-USDT"}),
    "okx_book": ("https://www.okx.com/api/v5/market/books", {"instId": "BTC-USDT", "sz": "20"}),
    "okx_funding": ("https://www.okx.com/api/v5/public/funding-rate", {"instId": "BTC-USDT-SWAP"}),
    "okx_oi": ("https://www.okx.com/api/v5/public/open-interest", {"instId": "BTC-USDT-SWAP"}),
    "okx_candles": ("https://www.okx.com/api/v5/market/candles", {"instId": "BTC-USDT", "bar": "1D", "limit": "20"}),
    "okx_mark_price": ("https://www.okx.com/api/v5/public/mark-price", {"instId": "BTC-USDT-SWAP"}),
    "okx_funding_history": ("https://www.okx.com/api/v5/public/funding-rate-history", {"instId": "BTC-USDT-SWAP", "limit": "20"}),
    "okx_liquidations": ("https://www.okx.com/api/v5/public/liquidation-orders", {
        "instType": "SWAP", "instFamily": "BTC-USDT", "state": "filled", "limit": "20",
    }),
    "coinbase_spot": ("https://api.coinbase.com/v2/prices/BTC-USD/spot", {}),
    "coinbase_usdinr": ("https://api.coinbase.com/v2/exchange-rates", {"currency": "USD"}),
    "bybit_ticker": ("https://api.bybit.com/v5/market/tickers", {"category": "spot", "symbol": "BTCUSDT"}),
    "kraken_ticker": ("https://api.kraken.com/0/public/Ticker", {"pair": "XBTUSD"}),
    "deribit_index": ("https://www.deribit.com/api/v2/public/get_index_price", {"index_name": "btc_usd"}),
    "deribit_options": ("https://www.deribit.com/api/v2/public/get_instruments", {
        "currency": "BTC", "kind": "option", "expired": "false",
    }),
    "deribit_dvol": ("https://www.deribit.com/api/v2/public/get_volatility_index_data", {
        "currency": "BTC", "resolution": "1D", "start_timestamp": "1795000000000",
        "end_timestamp": "1795700000000",
    }),
    "deribit_perp": ("https://www.deribit.com/api/v2/public/ticker", {
        "instrument_name": "BTC-PERPETUAL",
    }),
    "fear_greed": ("https://api.alternative.me/fng/", {"limit": "1"}),
    "paxg_spot": ("https://api.coingecko.com/api/v3/simple/price", {
        "ids": "pax-gold", "vs_currencies": "usd", "include_last_updated_at": "true",
    }),
}

POLICY_NAME = {
    "okx": "okx-public", "coinbase": "coinbase-public", "bybit": "bybit-public",
    "kraken": "kraken-public", "deribit": "deribit-public",
    "alternative": "alternative-sentiment", "coingecko": "coingecko-public",
}


def _policy_for_prefix(prefix: str) -> str:
    """Map a URL prefix to a declared policy; unknown sources get the strictest."""
    name = POLICY_NAME.get(prefix)
    return name if name in POLICIES_NAMES else "coingecko-public"


# Every policy name we may reference, including the existing crypto policy.
POLICIES_NAMES = frozenset(CAPABILITIES) | {"coingecko-public"}


def register_policies() -> None:
    """Declare conservative pacing for every new public source.

    Called from the API layer at startup. Existing policies are never replaced.
    """
    from .provider_policy import POLICIES, ProviderPolicy

    defaults = {
        "okx-public": (0.2, 4, 30.0),
        "coinbase-public": (1.0, 2, 30.0),
        "bybit-public": (0.5, 2, 30.0),
        "kraken-public": (0.5, 2, 30.0),
        "deribit-public": (0.5, 2, 60.0),
        "hyperliquid-public": (1.0, 2, 60.0),
        "alternative-sentiment": (2.0, 1, 3600.0),
        "coingecko-gold-token": (35.0, 1, 60.0),
    }
    for name, (interval, burst, ttl) in defaults.items():
        POLICIES.setdefault(name, ProviderPolicy(
            name=name, min_interval_seconds=interval, burst=burst,
            cache_ttl_seconds=ttl,
        ))


def _fetch(key: str) -> Any:
    """Fetch one public endpoint through the existing compliant limiter."""
    from .provider_policy import LIMITER

    path, params = _ENDPOINTS[key]
    url = path + ("?" + urllib.parse.urlencode(params) if params else "")
    prefix = key.split("_")[0]
    provider = _policy_for_prefix(prefix)
    if key == "paxg_spot":
        provider = "coingecko-gold-token"

    def call() -> Any:
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                raw = response.read(2_000_000)
        except urllib.error.HTTPError as exc:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            detail = f"{provider} returned HTTP {exc.code}"
            if retry_after:
                detail += f" (Retry-After: {retry_after}s)"
            raise ProviderError(detail) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"{provider} request failed: {exc}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderError(f"{provider} returned invalid JSON") from exc

    return LIMITER.call(provider, ("exchange", key), call)


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0 else None


def _quote(
    *,
    provider: str,
    symbol: str,
    last: float,
    observed_at: datetime,
    quote_type: str = "reference",
    currency: str = "USD",
    reason: str | None = None,
) -> MarketQuote:
    """Build a HISTORICAL quote; no attestation exists for these sources."""
    retrieved_at = datetime.now(timezone.utc)
    if observed_at > retrieved_at:
        observed_at = retrieved_at
    return MarketQuote(
        symbol=symbol.upper(), name=symbol.upper(), asset_class="digital_asset",
        market_group="crypto", exchange=provider, currency=currency,
        last=last, timestamp=observed_at, retrieved_at=retrieved_at,
        status=DataStatus.HISTORICAL, source=provider,
        quote_type=quote_type, reason=reason,
    )


def _unavailable(provider: str, symbol: str, reason: str) -> MarketQuote:
    now = datetime.now(timezone.utc)
    return unavailable_quote(
        symbol=symbol or "UNKNOWN", name=symbol or "Unknown", asset_class="digital_asset",
        market_group="crypto", exchange=provider, currency="USD",
        source=provider, reason=reason, timestamp=now,
    )


def venue_snapshot(venue: str, symbol: str = "BTCUSDT") -> dict[str, Any]:
    """Return a normalized, provenance-tagged snapshot for one venue.

    Raises ProviderError on an unusable response; callers convert it into an
    UNAVAILABLE observation. No data is cached here beyond the shared limiter.
    """
    venue = venue.strip().lower()
    now = datetime.now(timezone.utc)
    try:
        if venue == "okx":
            payload = _fetch("okx_ticker")
            row = (payload.get("data") or [{}])[0]
            price = _finite(row.get("last"))
            if price is None:
                raise ProviderError("okx-public returned no usable last price")
            return {
                "venue": venue, "symbol": symbol, "price": price,
                "bid": _finite(row.get("bidPx")), "ask": _finite(row.get("askPx")),
                "source": "okx-public", "observed_at": now, "status": "historical",
            }
        if venue == "coinbase":
            payload = _fetch("coinbase_spot")
            price = _finite((payload.get("data") or {}).get("amount"))
            if price is None:
                raise ProviderError("coinbase-public returned no usable spot price")
            return {
                "venue": venue, "symbol": symbol, "price": price,
                "source": "coinbase-public", "observed_at": now, "status": "historical",
            }
        if venue == "bybit":
            payload = _fetch("bybit_ticker")
            row = ((payload.get("result") or {}).get("list") or [{}])[0]
            price = _finite(row.get("lastPrice"))
            if price is None:
                raise ProviderError("bybit-public returned no usable last price")
            return {
                "venue": venue, "symbol": symbol, "price": price,
                "bid": _finite(row.get("bid1Price")), "ask": _finite(row.get("ask1Price")),
                "source": "bybit-public", "observed_at": now, "status": "historical",
            }
        if venue == "kraken":
            payload = _fetch("kraken_ticker")
            rows = payload.get("result") or {}
            row = next(iter(rows.values()), {})
            price = _finite((row.get("c") or [None])[0])
            if price is None:
                raise ProviderError("kraken-public returned no usable last price")
            return {
                "venue": venue, "symbol": symbol, "price": price,
                "source": "kraken-public", "observed_at": now, "status": "historical",
            }
        if venue == "deribit":
            payload = _fetch("deribit_index")
            price = _finite((payload.get("result") or {}).get("index_price"))
            if price is None:
                raise ProviderError("deribit-public returned no usable index price")
            return {
                "venue": venue, "symbol": "BTC-INDEX", "price": price,
                "source": "deribit-public", "observed_at": now, "status": "historical",
                "note": "Index price, not an executable quote.",
            }
        if venue == "hyperliquid":
            from .provider_policy import LIMITER

            body = json.dumps({"type": "allMids"}).encode()
            provider = "hyperliquid-public"
            register_policies()

            def call() -> Any:
                request = urllib.request.Request(
                    "https://api.hyperliquid.xyz/info", data=body,
                    headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
                )
                try:
                    with urllib.request.urlopen(request, timeout=8) as response:
                        return json.loads(response.read(2_000_000).decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    raise ProviderError(f"hyperliquid-public returned HTTP {exc.code}") from exc
                except (urllib.error.URLError, TimeoutError, OSError) as exc:
                    raise ProviderError(f"hyperliquid-public request failed: {exc}") from exc
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ProviderError("hyperliquid-public returned invalid JSON") from exc

            payload = LIMITER.call(provider, ("hyperliquid", "allMids"), call)
            price = _finite(payload.get("BTC"))
            if price is None:
                raise ProviderError("hyperliquid-public returned no BTC mid price")
            return {
                "venue": venue, "symbol": "BTC", "price": price,
                "source": "hyperliquid-public", "observed_at": now, "status": "historical",
            }
        raise ProviderError(f"unsupported venue: {venue}")
    except ProviderError:
        raise


def venue_quote(venue: str, symbol: str = "BTCUSDT") -> MarketQuote:
    """A MarketQuote for one venue, or an explicit UNAVAILABLE quote."""
    try:
        data = venue_snapshot(venue, symbol)
    except ProviderError as exc:
        provider = f"{venue}-public"
        return _unavailable(provider, symbol, str(exc))
    return _quote(
        provider=data["source"], symbol=data["symbol"], last=data["price"],
        observed_at=data["observed_at"],
    )


def funding_open_interest(symbol: str = "BTC-USDT-SWAP") -> dict[str, Any]:
    """OKX public funding rate and open interest, with explicit timestamps."""
    register_policies()
    try:
        funding = _fetch("okx_funding")
        oi = _fetch("okx_oi")
        frow = (funding.get("data") or [{}])[0]
        orow = (oi.get("data") or [{}])[0]
        rate = frow.get("fundingRate")
        try:
            rate_value = float(rate)
            if not math.isfinite(rate_value):
                raise ValueError
        except (TypeError, ValueError):
            raise ProviderError("okx-public returned an invalid funding rate")
        oi_value = _finite(orow.get("oiUsd"))
        if oi_value is None:
            raise ProviderError("okx-public returned no usable open interest")
        def stamp(value: Any, fallback: datetime) -> datetime:
            try:
                return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                return fallback
        return {
            "source": "okx-public", "symbol": symbol,
            "funding_rate": rate_value,
            "funding_time": stamp(frow.get("fundingTime"), datetime.now(timezone.utc)).isoformat(),
            "open_interest_usd": oi_value,
            "open_interest_time": stamp(orow.get("ts"), datetime.now(timezone.utc)).isoformat(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "historical", "status_label": "HISTORICAL",
            "note": "Public REST snapshots. No executable price or future-direction claim.",
        }
    except ProviderError as exc:
        return {
            "source": "okx-public", "symbol": symbol, "status": "unavailable",
            "status_label": "UNAVAILABLE", "reason": str(exc),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


def order_book_summary(symbol: str = "BTC-USDT", depth: int = 20) -> dict[str, Any]:
    """OKX public order-book depth summary. Displayed orders, not executed trades."""
    register_policies()
    try:
        payload = _fetch("okx_book")
        row = (payload.get("data") or [{}])[0]
        bids = row.get("bids") or []
        asks = row.get("asks") or []
        def total(levels: list) -> float:
            value = 0.0
            for level in levels[:depth]:
                if len(level) < 2:
                    continue
                price, size = _finite(level[0]), _finite(level[1])
                if price and size:
                    value += price * size
            return value
        bid_usd, ask_usd = total(bids), total(asks)
        total_usd = bid_usd + ask_usd
        return {
            "source": "okx-public", "symbol": symbol,
            "bid_depth_usd": round(bid_usd, 4), "ask_depth_usd": round(ask_usd, 4),
            "bid_levels": len(bids[:depth]), "ask_levels": len(asks[:depth]),
            "imbalance": round((bid_usd - ask_usd) / total_usd, 6) if total_usd else None,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "historical", "status_label": "HISTORICAL",
            "data_note": (
                "Displayed resting orders, not executed trades. Order-book "
                "imbalance is descriptive and is not evidence of future price direction."
            ),
        }
    except ProviderError as exc:
        return {
            "source": "okx-public", "symbol": symbol, "status": "unavailable",
            "status_label": "UNAVAILABLE", "reason": str(exc),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


def fear_greed_index() -> dict[str, Any]:
    """Alternative.me Fear & Greed daily index with attribution and timestamp."""
    register_policies()
    try:
        payload = _fetch("fear_greed")
        rows = payload.get("data") or []
        if not rows:
            raise ProviderError("alternative-sentiment returned no observations")
        row = rows[0]
        value = int(row.get("value"))
        if not 0 <= value <= 100:
            raise ProviderError("alternative-sentiment returned an out-of-range value")
        return {
            "source": "alternative-sentiment", "value": value,
            "classification": row.get("value_classification"),
            "timestamp": datetime.fromtimestamp(int(row["timestamp"]), tz=timezone.utc).isoformat(),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "historical", "status_label": "HISTORICAL",
            "note": "Daily sentiment indicator; not a price or trading signal.",
        }
    except (ProviderError, ValueError, KeyError, TypeError) as exc:
        return {
            "source": "alternative-sentiment", "status": "unavailable",
            "status_label": "UNAVAILABLE", "reason": str(exc),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
        }


def gold_token_quote() -> MarketQuote:
    """PAX Gold token quote — explicitly NOT spot or futures gold."""
    register_policies()
    try:
        payload = _fetch("paxg_spot")
        row = payload.get("pax-gold") or {}
        price = _finite(row.get("usd"))
        if price is None:
            raise ProviderError("coingecko-gold-token returned no usable price")
        observed = datetime.fromtimestamp(int(row["last_updated_at"]), tz=timezone.utc)
        quote = _quote(
            provider="coingecko-gold-token", symbol="PAXG", last=price,
            observed_at=observed, quote_type="reference",
        )
        return quote
    except (ProviderError, ValueError, KeyError, TypeError, OverflowError) as exc:
        return _unavailable("coingecko-gold-token", "PAXG", str(exc))


def capabilities_manifest() -> dict[str, Any]:
    register_policies()
    return {
        "mode": "public_exchange_intelligence",
        "adapters": [cap.to_payload() for cap in CAPABILITIES.values()],
        "observed_third_party_endpoints": [
            "data.tredye.com/data/live.json", "/api/cfno/okx",
        ],
        "third_party_endpoints_used": False,
        "note": (
            "Official public endpoints only. No broker credentials, no order "
            "execution, no undocumented endpoints, no limit bypass. Tredye's "
            "observed endpoints are research leads and are never called."
        ),
        "execution": {"broker_execution": False, "real_money": False},
    }


# ---------------------------------------------------------------------------
# EXTENSION: additional verified public research observations.
# Every function below uses the existing `_fetch` (and therefore the shared
# policy limiter), returns typed JSON-safe data, and never invents values.
# ---------------------------------------------------------------------------

def _as_epoch_ms(value: Any, fallback: datetime) -> datetime:
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return fallback


def okx_mark_price(symbol: str = "BTC-USDT-SWAP") -> dict[str, Any]:
    """OKX public mark price — a reference value, not an executable quote."""
    try:
        row = ((_fetch("okx_mark_price").get("data") or [{}])[0])
        price = _finite(row.get("markPx"))
        if price is None:
            raise ProviderError("okx-public returned no usable mark price")
        now = datetime.now(timezone.utc)
        return {
            "source": "okx-public", "symbol": symbol, "mark_price": price,
            "event_time": _as_epoch_ms(row.get("ts"), now).isoformat(),
            "retrieved_at": now.isoformat(), "status": "historical",
            "status_label": "HISTORICAL",
            "note": "Mark price is a reference value; not an executable quote.",
        }
    except ProviderError as exc:
        return {"source": "okx-public", "symbol": symbol, "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


def okx_funding_history(symbol: str = "BTC-USDT-SWAP") -> dict[str, Any]:
    """Current-period funding-rate history from OKX public REST."""
    try:
        rows = _fetch("okx_funding_history").get("data") or []
        observations = []
        for row in rows:
            try:
                rate = float(row.get("fundingRate"))
                if not math.isfinite(rate):
                    continue
            except (TypeError, ValueError):
                continue
            observations.append({
                "symbol": row.get("instId", symbol),
                "funding_rate": rate,
                "funding_time": _as_epoch_ms(
                    row.get("fundingTime"), datetime.now(timezone.utc)
                ).isoformat(),
                "method": row.get("method"),
            })
        if not observations:
            raise ProviderError("okx-public returned no usable funding history")
        return {
            "source": "okx-public", "symbol": symbol, "observations": observations,
            "count": len(observations), "status": "historical",
            "status_label": "HISTORICAL",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "note": "Funding rate is a derivation from the venue, not a price prediction.",
        }
    except ProviderError as exc:
        return {"source": "okx-public", "symbol": symbol, "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


def okx_liquidations(inst_family: str = "BTC-USDT") -> dict[str, Any]:
    """Recent filled liquidation orders from OKX public REST."""
    try:
        rows = _fetch("okx_liquidations").get("data") or []
        events = []
        for row in rows:
            for detail in row.get("details") or []:
                price = _finite(detail.get("bkPx"))
                size = _finite(detail.get("sz"))
                if price is None or size is None:
                    continue
                events.append({
                    "symbol": row.get("instId", inst_family),
                    "side": detail.get("posSide"),
                    "price": price, "size": size,
                    "notional": round(price * size, 6),
                    "event_time": _as_epoch_ms(
                        detail.get("ts"), datetime.now(timezone.utc)
                    ).isoformat(),
                })
        return {
            "source": "okx-public", "inst_family": inst_family,
            "events": events[:100], "count": len(events),
            "status": "historical", "status_label": "HISTORICAL",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "note": "Public liquidation feed; not all venue liquidations may be reported.",
        }
    except ProviderError as exc:
        return {"source": "okx-public", "inst_family": inst_family,
                "status": "unavailable", "status_label": "UNAVAILABLE",
                "reason": str(exc), "retrieved_at": datetime.now(timezone.utc).isoformat()}


def okx_candles(limit: int = 20) -> dict[str, Any]:
    """Daily OHLC candles from OKX public REST; explicit interval label."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    try:
        rows = _fetch("okx_candles").get("data") or []
        candles = []
        for row in rows[:limit]:
            if not isinstance(row, list) or len(row) < 6:
                continue
            bar = []
            for value in row[:6]:
                try:
                    number = float(value)
                except (TypeError, ValueError):
                    bar = []
                    break
                if not math.isfinite(number):
                    bar = []
                    break
                bar.append(number)
            if not bar:
                continue
            candles.append({
                "timestamp": datetime.fromtimestamp(bar[0] / 1000, tz=timezone.utc).isoformat(),
                "open": bar[1], "high": bar[2], "low": bar[3], "close": bar[4],
                "volume": bar[5],
            })
        if not candles:
            raise ProviderError("okx-public returned no usable candles")
        return {
            "source": "okx-public", "symbol": "BTC-USDT", "interval": "1d",
            "observed_interval": "1D", "candles": candles, "count": len(candles),
            "status": "historical", "status_label": "HISTORICAL",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "note": "Requested 1D candles; interval is provider-supplied, not resampled here.",
        }
    except ProviderError as exc:
        return {"source": "okx-public", "symbol": "BTC-USDT", "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


def deribit_options_summary(limit: int = 20) -> dict[str, Any]:
    """Options instrument metadata from Deribit public API (not a chain quote)."""
    if not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    try:
        rows = _fetch("deribit_options").get("result") or []
        instruments = [{
            "instrument_name": row.get("instrument_name"),
            "kind": row.get("kind"),
            "strike": row.get("strike"),
            "option_type": row.get("option_type"),
            "expiry_timestamp": (
                datetime.fromtimestamp(row["expiration_timestamp"] / 1000, tz=timezone.utc).isoformat()
                if row.get("expiration_timestamp") else None
            ),
        } for row in rows[:limit] if isinstance(row, dict)]
        return {
            "source": "deribit-public", "instruments": instruments,
            "count": len(instruments), "status": "historical",
            "status_label": "HISTORICAL",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "note": "Instrument metadata only; no implied volatility or bid/ask is claimed.",
        }
    except (ProviderError, ValueError, TypeError, OverflowError) as exc:
        return {"source": "deribit-public", "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


def deribit_volatility_index() -> dict[str, Any]:
    """Deribit BTC DVOL index observations from the public API."""
    try:
        result = _fetch("deribit_dvol").get("result") or {}
        rows = result.get("data") or []
        observations = []
        for row in rows[:100]:
            if not isinstance(row, list) or len(row) < 5:
                continue
            try:
                values = [float(value) for value in row[:5]]
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(value) for value in values):
                continue
            observations.append({
                "timestamp": datetime.fromtimestamp(values[0] / 1000, tz=timezone.utc).isoformat(),
                "open": values[1], "high": values[2], "low": values[3], "close": values[4],
            })
        return {
            "source": "deribit-public", "index": "BTC DVOL",
            "observations": observations, "count": len(observations),
            "status": "historical", "status_label": "HISTORICAL",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "note": "Published volatility index, not a model-derived implied vol.",
        }
    except (ProviderError, ValueError, TypeError, OverflowError) as exc:
        return {"source": "deribit-public", "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


def deribit_perpetual_summary() -> dict[str, Any]:
    """BTC-PERPETUAL public ticker summary from Deribit."""
    try:
        result = _fetch("deribit_perp").get("result") or {}
        last = _finite(result.get("last_price"))
        if last is None:
            raise ProviderError("deribit-public returned no perpetual last price")
        stats = result.get("stats") or {}
        return {
            "source": "deribit-public", "instrument": "BTC-PERPETUAL",
            "last": last,
            "price_change": stats.get("price_change"),
            "volume": stats.get("volume"),
            "event_time": (
                datetime.fromtimestamp(result["timestamp"] / 1000, tz=timezone.utc).isoformat()
                if result.get("timestamp") else None
            ),
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "historical", "status_label": "HISTORICAL",
            "note": "Perpetual ticker summary, not an executable quote.",
        }
    except (ProviderError, ValueError, TypeError, OverflowError) as exc:
        return {"source": "deribit-public", "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


def coinbase_usd_inr_reference() -> dict[str, Any]:
    """Coinbase USD/INR reference rate — explicitly NOT an executable FX quote."""
    try:
        rates = (_fetch("coinbase_usdinr").get("data") or {}).get("rates") or {}
        rate = _finite(rates.get("INR"))
        if rate is None:
            raise ProviderError("coinbase-public returned no USD/INR reference rate")
        return {
            "source": "coinbase-public", "pair": "USD/INR", "rate_type": "reference",
            "rate": rate,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "status": "reference", "status_label": "REFERENCE",
            "note": "Informational reference rate only; not an executable forex quote.",
        }
    except ProviderError as exc:
        return {"source": "coinbase-public", "pair": "USD/INR", "status": "unavailable",
                "status_label": "UNAVAILABLE", "reason": str(exc),
                "retrieved_at": datetime.now(timezone.utc).isoformat()}


UNAVAILABLE_EXCHANGE_ENDPOINTS = {
    "okx_taker_volume": "endpoint returned HTTP 404 during verification",
    "okx_global_long_short_ratio": "endpoint returned HTTP 404 during verification",
}

# Register every declared policy at import time. This makes all research
# functions safe to call directly (not only through the API layer), while the
# limiter itself remains the single source of pacing/caching enforcement.
register_policies()
