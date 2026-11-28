"""Unified four-market OHLCV ingestion with normalized provenance.

This module is the *only* place that turns provider observations into stored
OHLCV bars for the four-market terminal. It deliberately keeps the quote
adapters separate: a quote is an instant, a bar is an interval, and mixing
them would let a stale daily close masquerade as a current price.

Market / source mapping
-----------------------

* ``us``     — Yahoo chart v8 (daily and intraday), via ``YahooFinanceAdapter``.
* ``india``  — Yahoo chart v8 with NSE ``.NS`` / BSE ``.BO`` suffixes.
* ``forex``  — ECB EXR daily reference fixing. One fixing per business day; a
  bar with open=high=low=close is an honest representation of a *single fixing*,
  not an invented intraday range. Only ``1d`` is supported.
* ``crypto`` — CoinGecko public OHLC endpoint under the strict public rate
  policy. The provider returns candles for several timeframes; we request only
  the intervals we can actually honour and never manufacture candles.

Every batch is labelled ``HISTORICAL`` unless an operator has attested the
exact adapter name. Failed/unusable responses raise a typed error and produce
no bars: an empty series is reported, never filled.
"""
from __future__ import annotations

import csv
import io
import json
import math
import urllib.parse
from datetime import datetime, timedelta, timezone
from typing import Any

from . import market_store
from .market_data import DataStatus, MarketDataBatch, OHLCVBar
from .provider_adapters import ADAPTERS, ProviderError

# The limiter is imported at call sites, not here, so tests can replace it and
# so a cache reset always affects the live policy instance.

SUPPORTED_INTERVALS: tuple[str, ...] = ("15m", "1h", "4h", "1d")

# CoinGecko OHLC accepts day counts, not arbitrary interval strings. We map
# only the intervals we can honour without fabricating candles.
_COINGECKO_DAYS: dict[str, int] = {"15m": 1, "1h": 1, "4h": 7, "1d": 30}
_COINE_IDS: dict[str, str] = {
    "BTCUSD": "bitcoin", "BTCUSDT": "bitcoin",
    "ETHUSD": "ethereum", "ETHUSDT": "ethereum",
    "SOLUSD": "solana",
}

# Exchange-local session timezone declared by provider metadata; used only for
# display, never to shift the normalized UTC instant.
EXCHANGE_TIMEZONES: dict[str, str] = {
    "us": "America/New_York",
    "india": "Asia/Kolkata",
}


class IngestionError(RuntimeError):
    """A provider could not supply usable candles. Never silently filled."""


def _provider_symbol(symbol: str, market_group: str, venue: str = "") -> str:
    normalized = symbol.strip().upper()
    if market_group == "india":
        if normalized in {"NIFTY50", "NIFTYBANK", "SENSEX"}:
            return {
                "NIFTY50": "^NSEI", "NIFTYBANK": "^NSEBANK", "SENSEX": "^BSESN",
            }[normalized]
        suffix = ".BO" if venue.strip().upper() == "BSE" else ".NS"
        return normalized + suffix
    if market_group == "us" and normalized in {"SPX", "NDX", "US10Y"}:
        return {"SPX": "^GSPC", "NDX": "^NDX", "US10Y": "^TNX"}[normalized]
    return normalized


def _validate_interval(interval: str) -> str:
    value = interval.strip().lower()
    if value not in SUPPORTED_INTERVALS:
        raise ValueError("interval must be one of 15m,1h,4h,1d")
    return value


def _valid_bar(timestamp: datetime, o: Any, h: Any, l: Any, c: Any, v: Any) -> OHLCVBar | None:
    """Return a validated bar or None. Invalid candles are dropped, never fixed."""
    try:
        values = [float(o), float(h), float(l), float(c), float(v)]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in values):
        return None
    open_, high, low, close, volume = values
    if min(open_, high, low, close) <= 0 or volume < 0:
        return None
    if high < max(open_, low, close) or low > min(open_, high, close):
        return None
    return OHLCVBar(
        timestamp=timestamp, open=open_, high=high, low=low,
        close=close, volume=volume,
    )


def _yahoo_bars(symbol: str, interval: str, market_group: str,
                venue: str, limit: int) -> MarketDataBatch:
    from .yahoo_finance_adapter import YahooFinanceAdapter

    provider_symbol = _provider_symbol(symbol, market_group, venue)
    batch = YahooFinanceAdapter().get_bars_sync(provider_symbol, interval, limit)
    # Re-source the batch under the four-market adapter name so provenance is
    # explicit in the terminal (the underlying transport is unchanged).
    return MarketDataBatch(
        symbol=symbol.strip().upper(), interval=interval, status=batch.status,
        source=ADAPTERS[market_group].capability.name,
        retrieved_at=batch.retrieved_at, bars=batch.bars,
        warnings=batch.warnings + [
            "Symbol mapped to provider convention " + provider_symbol,
            "Exchange timezone " + EXCHANGE_TIMEZONES.get(market_group, "unspecified"),
        ],
    )


def _ecb_bars(symbol: str, interval: str, limit: int) -> MarketDataBatch:
    """Daily EUR-based reference fixings as honest single-price bars."""
    text = "".join(ch for ch in symbol.strip().upper() if ch.isalpha())
    if len(text) != 6:
        raise IngestionError("forex symbol must be a six-letter currency pair")
    if interval != "1d":
        raise IngestionError("ECB reference rates support only the 1d interval")
    base, quote = text[:3], text[3:]
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=90)
    query = urllib.parse.urlencode({
        "format": "csvdata", "startPeriod": start.isoformat(),
        "endPeriod": end.isoformat(),
    })
    url = (
        "https://data-api.ecb.europa.eu/service/data/EXR/"
        f"D.{quote}.EUR.SP00.A?{query}"
    )
    from .provider_policy import LIMITER

    body = LIMITER.call("ecb-reference-rates", ("ecb", url), lambda: _ecb_get(url))
    try:
        rows = list(csv.DictReader(io.StringIO(body)))
    except csv.Error as exc:
        raise IngestionError("ECB returned unparsable CSV") from exc
    bars: list[OHLCVBar] = []
    for row in rows:
        raw = (row.get("OBS_VALUE") or "").strip()
        period = (row.get("TIME_PERIOD") or "").strip()
        try:
            value = float(raw)
            observed = datetime.fromisoformat(period).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
        if not math.isfinite(value) or value <= 0:
            continue
        # A reference fixing is one observation. open=high=low=close is the
        # honest representation; we never invent a range that wasn't published.
        bar = _valid_bar(observed, value, value, value, value, 0)
        if bar is not None:
            bars.append(bar)
    if not bars:
        raise IngestionError(f"ECB returned no usable daily fixings for {quote}/EUR")
    bars.sort(key=lambda bar: bar.timestamp)
    bars = bars[-limit:]
    return MarketDataBatch(
        symbol=symbol.strip().upper(), interval="1d", status=DataStatus.HISTORICAL,
        source=ADAPTERS["forex"].capability.name,
        retrieved_at=datetime.now(timezone.utc), bars=bars,
        warnings=[
            "ECB publishes one reference fixing per business day.",
            "open=high=low=close represents a single published fixing, not an intraday range.",
            "A fixing is informational; it is not an executable price.",
        ],
    )


def _ecb_get(url: str) -> str:
    import urllib.request

    from .provider_adapters import USER_AGENT

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/csv"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.read(4_000_000).decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise ProviderError(f"ecb-reference-rates returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"ecb-reference-rates request failed: {exc}") from exc


def _coingecko_bars(symbol: str, interval: str, limit: int) -> MarketDataBatch:
    coin = _COINE_IDS.get(symbol.strip().upper())
    if coin is None:
        raise IngestionError("symbol is not mapped to a public CoinGecko asset id")
    days = _COINGECKO_DAYS[interval]
    query = urllib.parse.urlencode({"vs_currency": "usd", "days": str(days)})
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/ohlc?{query}"
    from .provider_policy import LIMITER

    body = LIMITER.call("coingecko-public", ("coingecko-ohlc", url), lambda: _get_json(url))
    if not isinstance(body, list):
        raise IngestionError("CoinGecko OHLC response was not a candle array")
    bars: list[OHLCVBar] = []
    for row in body:
        if not isinstance(row, list) or len(row) < 5:
            continue
        try:
            timestamp = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
        except (ValueError, TypeError, OverflowError):
            continue
        # CoinGecko's public OHLC payload has no volume field. Volume=0 is an
        # explicit "not provided" marker, never a claim of zero trading.
        bar = _valid_bar(timestamp, row[1], row[2], row[3], row[4], 0)
        if bar is not None:
            bars.append(bar)
    if not bars:
        raise IngestionError("CoinGecko returned no usable OHLC candles")
    bars.sort(key=lambda bar: bar.timestamp)
    bars = bars[-limit:]
    return MarketDataBatch(
        symbol=symbol.strip().upper(), interval=interval, status=DataStatus.HISTORICAL,
        source=ADAPTERS["crypto"].capability.name,
        retrieved_at=datetime.now(timezone.utc), bars=bars,
        warnings=[
            "CoinGecko OHLC is an aggregated cross-venue snapshot, not one venue's tape.",
            "The public OHLC payload omits volume; volume=0 explicitly means 'not provided'.",
            "Public plan rate limits apply; requests are paced and cached under a strict policy.",
            "Historical research only; no executable bid/ask or trading signal.",
        ],
    )


def _get_json(url: str) -> Any:
    import urllib.request

    from .provider_adapters import USER_AGENT

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read(4_000_000).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        detail = f"coingecko-public returned HTTP {exc.code}"
        if retry_after:
            detail += f" (Retry-After: {retry_after}s)"
        raise ProviderError(detail) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ProviderError(f"coingecko-public request failed: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError("coingecko-public returned invalid JSON") from exc


def ingest_bars(
    symbol: str,
    market_group: str,
    interval: str = "1d",
    limit: int = 100,
    venue: str = "",
    *,
    store: bool = True,
) -> dict[str, Any]:
    """Fetch, normalize and (optionally) store OHLCV bars for one instrument."""
    group = market_group.strip().lower()
    if group not in ADAPTERS:
        raise ValueError("market_group must be one of india, us, crypto, forex")
    value = _validate_interval(interval)
    if not 1 <= limit <= 5000:
        raise ValueError("limit must be between 1 and 5000")
    if not symbol.strip() or len(symbol) > 32:
        raise ValueError("symbol must contain 1 to 32 characters")

    try:
        if group in ("us", "india"):
            batch = _yahoo_bars(symbol, value, group, venue, limit)
        elif group == "forex":
            batch = _ecb_bars(symbol, value, limit)
        else:
            batch = _coingecko_bars(symbol, value, limit)
    except IngestionError as exc:
        raise IngestionError(str(exc)) from exc

    storage = market_store.store_batch(batch) if store else None
    return {
        "mode": "four_market_historical_ingestion",
        "symbol": batch.symbol,
        "market_group": group,
        "venue": venue or None,
        "interval": batch.interval,
        "source": batch.source,
        "status": batch.status.value,
        "status_label": "HISTORICAL",
        "retrieved_at": batch.retrieved_at.isoformat(),
        "observation_count": len(batch.bars),
        "first_timestamp": batch.bars[0].timestamp.isoformat() if batch.bars else None,
        "last_timestamp": batch.bars[-1].timestamp.isoformat() if batch.bars else None,
        "exchange_timezone": EXCHANGE_TIMEZONES.get(group),
        "storage": storage,
        "warnings": batch.warnings,
        "bars": [bar.model_dump(mode="json") for bar in batch.bars],
        "execution": {
            "paper_trading": False, "broker_execution": False, "real_money": False,
        },
    }


def interval_support(market_group: str) -> dict[str, Any]:
    group = market_group.strip().lower()
    if group not in ADAPTERS:
        raise ValueError("market_group must be one of india, us, crypto, forex")
    if group == "forex":
        supported, note = ("1d",), "ECB publishes one fixing per business day."
    else:
        supported, note = SUPPORTED_INTERVALS, (
            "CoinGecko OHLC uses day-based windows mapped to these intervals."
            if group == "crypto" else "Yahoo chart endpoint supports these intervals."
        )
    return {
        "market_group": group,
        "source": ADAPTERS[group].capability.name,
        "supported_intervals": list(supported),
        "exchange_timezone": EXCHANGE_TIMEZONES.get(group),
        "note": note,
    }
