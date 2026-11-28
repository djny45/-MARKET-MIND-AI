"""Four-market provider adapters behind one normalized contract.

Each adapter covers exactly one of the four first-class research domains:

============================  ====================  ==============================
Market group                  Adapter               Native observation
============================  ====================  ==============================
``us``                        ``yahoo-us-equities`` NYSE/NASDAQ/ETF/index daily bars
``india``                     ``yahoo-india-nse-bse`` NSE ``.NS`` / BSE ``.BO`` series
``forex``                     ``ecb-reference-rates`` ECB daily reference fixing
``crypto``                    ``coingecko-public``  public spot snapshot
============================  ====================  ==============================

Design rules enforced here, not left to callers:

* **No fabricated prices.** A failed, unparsable or unlicensed fetch returns an
  explicit ``UNAVAILABLE`` quote carrying the reason. It never returns a zero,
  a cached guess or a synthetic number.
* **Attestation decides the label.** An adapter declares the best label it can
  honestly support (``preferred_status``). It may only *claim* ``LIVE`` or
  ``DELAYED`` when the operator has attested that source name. Otherwise the
  same observation is labelled ``HISTORICAL``. Labels are never self-assigned.
* **Event time and ingestion time stay separate.** Every quote keeps the
  provider's own observation timestamp alongside ``retrieved_at``.
* **No credentials.** All four endpoints are public and unauthenticated. This
  module reads no secret and logs none.

Network access is confined to ``_get_json``/``_get_text`` so tests can patch a
single seam per adapter and never touch the internet.
"""
from __future__ import annotations

import csv
import io
import json
import math
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .market_data import DataStatus
from .market_quotes import MarketQuote, unavailable_quote

USER_AGENT = "MARKET-MIND-AI research adapter/1.0 (+research-only)"
MAX_RESPONSE_BYTES = 4_000_000


class ProviderError(RuntimeError):
    """Raised for provider transport/parse failures; never leaks a URL secret."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class ProviderCapability:
    """Declared, testable facts about one adapter."""

    name: str
    market_group: str
    asset_classes: tuple[str, ...]
    native_granularity: str
    preferred_status: DataStatus
    requires_attestation: bool
    licensing_note: str
    limitations: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "market_group": self.market_group,
            "asset_classes": list(self.asset_classes),
            "native_granularity": self.native_granularity,
            "preferred_status": self.preferred_status.value,
            "requires_attestation": self.requires_attestation,
            "licensing_note": self.licensing_note,
            "limitations": list(self.limitations),
            "credentials_required": False,
        }


class _HttpAdapter:
    """Shared, mockable HTTP seam. Public endpoints only, no credentials."""

    capability: ProviderCapability
    timeout_seconds: float = 10.0

    def __init__(self, timeout_seconds: float = 10.0) -> None:
        if not 1 <= timeout_seconds <= 30:
            raise ValueError("timeout_seconds must be between 1 and 30")
        self.timeout_seconds = timeout_seconds

    # -- transport -------------------------------------------------------
    def _raw_get(self, url: str, *, accept: str) -> str:
        """One actual HTTP request. Never called directly by application code."""
        request = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT, "Accept": accept}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES)
        except urllib.error.HTTPError as exc:
            # Surface the provider's own Retry-After so an operator can tell a
            # rate limit from an outage. The limiter then honours it literally.
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            detail = f"{self.capability.name} returned HTTP {exc.code}"
            if retry_after:
                detail += f" (Retry-After: {retry_after}s)"
            raise ProviderError(detail) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProviderError(f"{self.capability.name} request failed: {exc}") from exc
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProviderError(f"{self.capability.name} returned non-UTF-8 data") from exc

    def _get(self, url: str, *, accept: str) -> str:
        """Fetch under the declared per-provider pacing, retry and cache policy.

        Tests patch this method, bypassing transport. Production callers always
        pass through the limiter, so a 429 can never be retried around a
        provider's Retry-After deadline.
        """
        from .provider_policy import LIMITER

        return LIMITER.call(
            self.capability.name, (self.capability.name, url, accept),
            lambda: self._raw_get(url, accept=accept),
        )

    def _get_json(self, url: str) -> Any:
        body = self._get(url, accept="application/json")
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"{self.capability.name} returned invalid JSON") from exc

    # -- status selection ------------------------------------------------
    def resolve_status(
        self, attested_sources: Iterable[str], *, preferred: DataStatus | None = None
    ) -> DataStatus:
        """Return the strongest label this observation may honestly carry.

        An unattested source can never claim LIVE/DELAYED, so the observation
        degrades to HISTORICAL rather than being dressed up.
        """
        attested = {value.strip().lower() for value in attested_sources if value and value.strip()}
        wanted = preferred or self.capability.preferred_status
        if wanted in (DataStatus.LIVE, DataStatus.DELAYED):
            if self.capability.name.lower() in attested:
                return wanted
            return DataStatus.HISTORICAL
        return wanted

    # -- helpers ---------------------------------------------------------
    @staticmethod
    def _finite(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _quote(self, **kwargs: Any) -> MarketQuote:
        return MarketQuote(**kwargs)

    def unavailable(self, *, reason: str, **kwargs: Any) -> MarketQuote:
        """Build an UNAVAILABLE quote attributed to this adapter."""
        return unavailable_quote(source=self.capability.name, reason=reason, **kwargs)


# ---------------------------------------------------------------------------
# United States: Yahoo chart endpoint (NYSE / NASDAQ / ETFs / indices)
# ---------------------------------------------------------------------------

_US_SYMBOL_MAP = {
    "SPX": "^GSPC",
    "NDX": "^NDX",
    "US10Y": "^TNX",
    "SPY": "SPY",
    "QQQ": "QQQ",
}


class UsEquitiesAdapter(_HttpAdapter):
    """NYSE/NASDAQ equities, ETFs and indices via the Yahoo chart endpoint."""

    capability = ProviderCapability(
        name="yahoo-us-equities",
        market_group="us",
        asset_classes=("equities", "funds", "indices"),
        native_granularity="1d",
        preferred_status=DataStatus.DELAYED,
        requires_attestation=True,
        licensing_note=(
            "Community-facing Yahoo chart endpoint. Best-effort and unofficial; "
            "attestation is required before claiming live or delayed status."
        ),
        limitations=(
            "Unofficial endpoint; upstream availability and terms can change.",
            "Not execution-grade and not a licensed real-time feed.",
        ),
    )

    def provider_symbol(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        return _US_SYMBOL_MAP.get(normalized, normalized)

    def _chart_url(self, provider_symbol: str) -> str:
        encoded = urllib.parse.quote(provider_symbol, safe="")
        query = urllib.parse.urlencode({"interval": "1d", "range": "5d", "events": "history"})
        return f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?{query}"

    def fetch_quote(
        self, *, symbol: str, name: str, asset_class: str = "equity",
        exchange: str = "NASDAQ", currency: str = "USD",
        attested_sources: Iterable[str] = (), instrument_id: str | None = None,
    ) -> MarketQuote:
        retrieved_at = _utc_now()
        try:
            payload = self._get_json(self._chart_url(self.provider_symbol(symbol)))
            timestamp, close, previous, tz_name = _parse_yahoo_daily(payload)
        except ProviderError as exc:
            return self.unavailable(
                symbol=symbol, name=name, asset_class=asset_class,
                market_group="us", exchange=exchange, currency=currency,
                reason=str(exc), timestamp=retrieved_at, instrument_id=instrument_id,
            )
        status = self.resolve_status(attested_sources)
        change = None
        if previous and previous > 0:
            change = round((close - previous) / previous * 100, 4)
        return self._quote(
            symbol=symbol, name=name, asset_class=asset_class, market_group="us",
            exchange=exchange, currency=currency, instrument_id=instrument_id,
            last=close, change_pct=change, timestamp=timestamp,
            retrieved_at=retrieved_at, status=status,
            source=self.capability.name,
            quote_type="close",
            exchange_timezone=tz_name,
            delay_seconds=0 if status is DataStatus.LIVE else None,
            attested_sources=frozenset(attested_sources),
        )


def _parse_yahoo_daily(payload: Any) -> tuple[datetime, float, float | None, str | None]:
    """Return (event time, last close, previous close, IANA exchange timezone)."""
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ProviderError("US provider returned no chart result") from exc
    # The exchange timezone is provider-declared metadata. Validate it here so
    # an unexpected value becomes "unknown" rather than a guessed timezone.
    tz_name = (result.get("meta") or {}).get("exchangeTimezoneName")
    if isinstance(tz_name, str) and tz_name.strip():
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(tz_name.strip())
            tz_name = tz_name.strip()
        except (ZoneInfoNotFoundError, ValueError):
            tz_name = None
    else:
        tz_name = None
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    closes = quote.get("close") or []
    pairs: list[tuple[datetime, float]] = []
    for index, stamp in enumerate(stamps):
        if index >= len(closes):
            break
        value = closes[index]
        if value is None or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            continue
        pairs.append((datetime.fromtimestamp(int(stamp), tz=timezone.utc), float(value)))
    if not pairs:
        raise ProviderError("US provider returned no usable daily close")
    pairs.sort(key=lambda item: item[0])
    previous = pairs[-2][1] if len(pairs) >= 2 else None
    return pairs[-1][0], pairs[-1][1], previous, tz_name


# ---------------------------------------------------------------------------
# India: Yahoo chart endpoint with NSE (.NS) / BSE (.BO) suffixes
# ---------------------------------------------------------------------------

_INDIA_SYMBOL_MAP = {
    "NIFTY50": "^NSEI",
    "NIFTYBANK": "^NSEBANK",
    "SENSEX": "^BSESN",
}


class IndiaEquitiesAdapter(_HttpAdapter):
    """NSE/BSE equities and indices via Yahoo's exchange-suffixed symbols."""

    capability = ProviderCapability(
        name="yahoo-india-nse-bse",
        market_group="india",
        asset_classes=("equities", "indices"),
        native_granularity="1d",
        preferred_status=DataStatus.DELAYED,
        requires_attestation=True,
        licensing_note=(
            "NSE and BSE publish distinct real-time, snapshot, end-of-day and "
            "historical products under their own data policy. A public webpage "
            "or an unofficial endpoint is not redistribution permission; "
            "attestation and a licence review are required before claiming "
            "live or delayed status for Indian exchange data."
        ),
        limitations=(
            "Yahoo coverage of Indian symbols is incomplete and unofficial.",
            "NSE/BSE session, holiday and corporate-action handling is not applied.",
            "Symbol suffixes are a provider convention, not an exchange identity.",
        ),
    )

    def provider_symbol(self, symbol: str, exchange: str = "NSE") -> str:
        normalized = symbol.strip().upper()
        if normalized in _INDIA_SYMBOL_MAP:
            return _INDIA_SYMBOL_MAP[normalized]
        suffix = ".BO" if exchange.strip().upper() == "BSE" else ".NS"
        return normalized + suffix

    def _chart_url(self, provider_symbol: str) -> str:
        encoded = urllib.parse.quote(provider_symbol, safe="")
        query = urllib.parse.urlencode({"interval": "1d", "range": "5d", "events": "history"})
        return f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?{query}"

    def fetch_quote(
        self, *, symbol: str, name: str, asset_class: str = "equity",
        exchange: str = "NSE", currency: str = "INR",
        attested_sources: Iterable[str] = (), instrument_id: str | None = None,
    ) -> MarketQuote:
        retrieved_at = _utc_now()
        try:
            payload = self._get_json(self._chart_url(self.provider_symbol(symbol, exchange)))
            timestamp, close, previous, tz_name = _parse_yahoo_daily(payload)
        except ProviderError as exc:
            return self.unavailable(
                symbol=symbol, name=name, asset_class=asset_class,
                market_group="india", exchange=exchange, currency=currency,
                reason=str(exc), timestamp=retrieved_at, instrument_id=instrument_id,
            )
        status = self.resolve_status(attested_sources)
        change = round((close - previous) / previous * 100, 4) if previous and previous > 0 else None
        return self._quote(
            symbol=symbol, name=name, asset_class=asset_class, market_group="india",
            exchange=exchange, currency=currency, instrument_id=instrument_id,
            last=close, change_pct=change, timestamp=timestamp,
            retrieved_at=retrieved_at, status=status,
            source=self.capability.name, quote_type="close",
            exchange_timezone=tz_name,
            delay_seconds=0 if status is DataStatus.LIVE else None,
            attested_sources=frozenset(attested_sources),
        )


# ---------------------------------------------------------------------------
# Forex: ECB daily euro reference rates (reference fixing, never tradable)
# ---------------------------------------------------------------------------

class EcbForexAdapter(_HttpAdapter):
    """ECB euro reference rates: a daily reference fixing, not a tradable quote."""

    capability = ProviderCapability(
        name="ecb-reference-rates",
        market_group="forex",
        asset_classes=("fx",),
        native_granularity="1d",
        preferred_status=DataStatus.HISTORICAL,
        requires_attestation=False,
        licensing_note=(
            "ECB reference rates are published for information and are not "
            "executable prices. OTC FX has no consolidated tape; this adapter "
            "never claims a tradable bid/ask."
        ),
        limitations=(
            "One fixing per business day; no intraday observation.",
            "Quoted against EUR, so cross rates are derived by division.",
            "Not a dealer quote and not suitable for execution.",
        ),
    )

    def _url(self, currency: str) -> str:
        code = currency.strip().upper()
        series = f"D.{code}.EUR.SP00.A"
        query = urllib.parse.urlencode({"format": "csvdata", "lastNObservations": "2"})
        return f"https://data-api.ecb.europa.eu/service/data/EXR/{series}?{query}"

    def fetch_quote(
        self, *, symbol: str, name: str, currency: str = "USD",
        exchange: str = "OTC", asset_class: str = "fx",
        attested_sources: Iterable[str] = (),
        instrument_id: str | None = None,
    ) -> MarketQuote:
        retrieved_at = _utc_now()
        pair = _split_fx_pair(symbol)
        if pair is None:
            return self.unavailable(
                symbol=symbol, name=name, asset_class=asset_class, market_group="forex",
                exchange=exchange, currency=currency,
                reason="symbol is not a six-letter currency pair",
                timestamp=retrieved_at, instrument_id=instrument_id,
            )
        base, quote_currency = pair
        try:
            rate, observed_on = self._fetch_rate(base, quote_currency)
        except ProviderError as exc:
            return self.unavailable(
                symbol=symbol, name=name, asset_class=asset_class, market_group="forex",
                exchange=exchange, currency=quote_currency,
                reason=str(exc), timestamp=retrieved_at, instrument_id=instrument_id,
            )
        status = self.resolve_status(attested_sources)
        return self._quote(
            symbol=symbol, name=name, asset_class=asset_class, market_group="forex",
            exchange=exchange, currency=quote_currency, instrument_id=instrument_id,
            last=rate, timestamp=observed_on, retrieved_at=retrieved_at,
            status=status, source=self.capability.name, quote_type="reference",
            # ECB publishes a DATE, not a timezone-bearing instant. We carry no
            # IANA timezone claim: a reference fixing has no exchange session,
            # and inventing one would be false precision.
            exchange_timezone=None,
            attested_sources=frozenset(attested_sources),
        )

    def _fetch_rate(self, base: str, quote_currency: str) -> tuple[float, datetime]:
        """Return the pair rate using EUR as the pivot currency."""
        if base == "EUR" and quote_currency == "EUR":
            raise ProviderError("EUR/EUR is not a currency pair")
        if quote_currency == "EUR":
            # ECB quotes CCY per EUR, so EUR/CCY is the reciprocal.
            per_eur, observed_on = self._per_eur(base)
            return 1.0 / per_eur, observed_on
        if base == "EUR":
            return self._per_eur(quote_currency)
        base_per_eur, base_time = self._per_eur(base)
        quote_per_eur, quote_time = self._per_eur(quote_currency)
        return quote_per_eur / base_per_eur, min(base_time, quote_time)

    def _per_eur(self, currency: str) -> tuple[float, datetime]:
        body = self._get(self._url(currency), accept="text/csv")
        rows = [row for row in csv.DictReader(io.StringIO(body))]
        if not rows:
            raise ProviderError(f"ECB returned no observations for {currency.upper()}")
        latest = rows[-1]
        value = self._finite(latest.get("OBS_VALUE"))
        if value is None or value <= 0:
            raise ProviderError(f"ECB returned a non-positive rate for {currency.upper()}")
        period = (latest.get("TIME_PERIOD") or "").strip()
        try:
            observed_on = datetime.fromisoformat(period).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise ProviderError("ECB returned an unparsable reference date") from exc
        return value, observed_on


def _split_fx_pair(symbol: str) -> tuple[str, str] | None:
    text = "".join(ch for ch in symbol.strip().upper() if ch.isalpha())
    if len(text) != 6:
        return None
    return text[:3], text[3:]


# ---------------------------------------------------------------------------
# Crypto: CoinGecko public simple-price snapshot
# ---------------------------------------------------------------------------

_CRYPTO_ID_MAP = {
    "BTCUSD": ("bitcoin", "USD"),
    "BTCUSDT": ("bitcoin", "USD"),
    "ETHUSD": ("ethereum", "USD"),
    "ETHUSDT": ("ethereum", "USD"),
    "SOLUSD": ("solana", "USD"),
}


class CoinGeckoCryptoAdapter(_HttpAdapter):
    """Public spot snapshot for major crypto assets."""

    capability = ProviderCapability(
        name="coingecko-public",
        market_group="crypto",
        asset_classes=("digital_assets",),
        native_granularity="snapshot",
        preferred_status=DataStatus.DELAYED,
        requires_attestation=True,
        licensing_note=(
            "CoinGecko public API with rate limits and terms that vary by plan. "
            "Aggregated across venues, not a single-venue order book."
        ),
        limitations=(
            "Aggregated cross-venue price; not one exchange's tape.",
            "No bid/ask, depth or trade classification is provided.",
            "Public rate limits apply; repeated polling may be throttled.",
        ),
    )

    def coin_id(self, symbol: str) -> str | None:
        entry = _CRYPTO_ID_MAP.get(symbol.strip().upper())
        return entry[0] if entry else None

    def _url(self, coin_id: str) -> str:
        query = urllib.parse.urlencode({
            "ids": coin_id, "vs_currencies": "usd", "include_last_updated_at": "true",
        })
        return f"https://api.coingecko.com/api/v3/simple/price?{query}"

    # One batched request serves every crypto symbol in the terminal board.
    # The constant URL is cached by the existing provider_policy limiter (60s
    # TTL), so no second cache is needed. Keeping caching in one place also
    # preserves offline test isolation when _get_json is patched to fail.
    def _batch_url(self) -> str:
        ids = ",".join(sorted({value[0] for value in _CRYPTO_ID_MAP.values()}))
        query = urllib.parse.urlencode({
            "ids": ids, "vs_currencies": "usd", "include_last_updated_at": "true",
        })
        return f"https://api.coingecko.com/api/v3/simple/price?{query}"

    def fetch_quote(
        self, *, symbol: str, name: str, asset_class: str = "spot_crypto",
        exchange: str = "Multi-venue", currency: str = "USD",
        attested_sources: Iterable[str] = (), instrument_id: str | None = None,
    ) -> MarketQuote:
        retrieved_at = _utc_now()
        coin_id = self.coin_id(symbol)
        if coin_id is None:
            return self.unavailable(
                symbol=symbol, name=name, asset_class=asset_class, market_group="crypto",
                exchange=exchange, currency=currency,
                reason="symbol is not mapped to a public CoinGecko asset id",
                timestamp=retrieved_at, instrument_id=instrument_id,
            )
        try:
            payload = self._get_json(self._batch_url())
            entry = payload.get(coin_id) or {}
            price = self._finite(entry.get("usd"))
            stamp = self._finite(entry.get("last_updated_at"))
            if price is None or price <= 0:
                raise ProviderError(f"crypto provider returned no USD price for {coin_id}")
            if stamp is None:
                raise ProviderError("crypto provider omitted the observation timestamp")
            observed_at = datetime.fromtimestamp(int(stamp), tz=timezone.utc)
        except ProviderError as exc:
            return self.unavailable(
                symbol=symbol, name=name, asset_class=asset_class, market_group="crypto",
                exchange=exchange, currency=currency,
                reason=str(exc), timestamp=retrieved_at, instrument_id=instrument_id,
            )
        if observed_at > retrieved_at:
            observed_at = retrieved_at
        status = self.resolve_status(attested_sources)
        return self._quote(
            symbol=symbol, name=name, asset_class=asset_class, market_group="crypto",
            exchange=exchange, currency=currency, instrument_id=instrument_id,
            last=price, timestamp=observed_at, retrieved_at=retrieved_at,
            status=status, source=self.capability.name, quote_type="mid",
            attested_sources=frozenset(attested_sources),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

ADAPTERS: dict[str, _HttpAdapter] = {
    "us": UsEquitiesAdapter(),
    "india": IndiaEquitiesAdapter(),
    "forex": EcbForexAdapter(),
    "crypto": CoinGeckoCryptoAdapter(),
}


def adapters_for(market_group: str | None = None) -> list[_HttpAdapter]:
    if market_group is None:
        return [ADAPTERS[key] for key in ("us", "india", "forex", "crypto")]
    adapter = ADAPTERS.get(market_group.strip().lower())
    if adapter is None:
        raise ValueError("market_group must be one of india, us, crypto, forex")
    return [adapter]


def adapter_manifest() -> dict[str, Any]:
    """Capability manifest for the terminal UI and the provider status endpoint."""
    return {
        "mode": "four_market_normalized_adapters",
        "market_groups": ["us", "india", "forex", "crypto"],
        "adapters": [adapter.capability.to_payload() for adapter in adapters_for()],
        "credentials_required": False,
        "credentials_exposed": False,
        "live_claims_require_attestation": True,
        "note": (
            "All four adapters are public and unauthenticated. A source may only "
            "claim LIVE or DELAYED when the operator attests its exact adapter "
            "name; otherwise the same observation is labelled HISTORICAL. "
            "Failed fetches return UNAVAILABLE with a reason, never a price."
        ),
    }


def quotes_for_instruments(
    instruments: list[dict[str, Any]],
    *,
    attested_sources: Iterable[str] = (),
    max_workers: int = 4,
) -> list[MarketQuote]:
    """Fetch normalized quotes for reference instruments, one market group each.

    A per-symbol failure is contained: it becomes an UNAVAILABLE quote so one
    dead provider cannot blank the terminal. Different providers are fetched in
    parallel (the original sequential loop took ~20s), but requests to the SAME
    provider are serialized: a three-symbol crypto burst caused CoinGecko HTTP
    429 during validation. A provider that cannot be reached yields
    UNAVAILABLE with a reason, never a fabricated price.
    """
    attested = tuple(attested_sources)
    import threading

    provider_locks: dict[str, threading.Lock] = {}

    def lock_for(name: str) -> threading.Lock:
        # One lock per adapter. Different providers never contend.
        return provider_locks.setdefault(name, threading.Lock())

    def fetch_one(instrument: dict[str, Any]) -> MarketQuote:
        group = str(instrument.get("market_group") or "").strip().lower()
        adapter = ADAPTERS.get(group)
        symbol = str(instrument.get("symbol") or "").strip().upper()
        name = str(instrument.get("name") or symbol)
        asset_class = str(instrument.get("market") or "equity")
        exchange = str(instrument.get("venue") or "OTC")
        currency = str(instrument.get("currency") or "USD")
        instrument_id = instrument.get("instrument_id")
        if adapter is None:
            # The market group is not one of the four supported domains, so it
            # cannot be echoed into a validated field. The row is still reported
            # with no price and an explicit reason.
            return unavailable_quote(
                symbol=symbol or "UNKNOWN", name=name or "Unknown instrument",
                asset_class=asset_class, market_group=None,
                exchange=exchange, currency=currency,
                source="unrouted-market-group",
                reason=f"no adapter is registered for market group {group!r}",
                timestamp=_utc_now(), instrument_id=instrument_id,
            )
        try:
            # Serialize calls to the same public provider; this avoids the
            # 429 burst observed when three crypto symbols were fetched at once.
            with lock_for(adapter.capability.name):
                return adapter.fetch_quote(
                    symbol=symbol, name=name, asset_class=asset_class,
                    exchange=exchange, currency=currency,
                    attested_sources=attested, instrument_id=instrument_id,
                )
        except Exception as exc:  # noqa: BLE001 - containment is the point
            # One adapter bug must never blank the whole terminal. The failure
            # becomes an explicit UNAVAILABLE row naming the exception type.
            return unavailable_quote(
                symbol=symbol or "UNKNOWN", name=name or "Unknown instrument",
                asset_class=asset_class, market_group=group,
                exchange=exchange, currency=currency,
                source=adapter.capability.name,
                reason=f"adapter error ({type(exc).__name__}); no price is implied",
                timestamp=_utc_now(), instrument_id=instrument_id,
            )

    if not instruments:
        return []
    if len(instruments) == 1 or max_workers <= 1:
        return [fetch_one(item) for item in instruments]
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=min(max_workers, len(instruments))) as pool:
        # executor.map preserves the caller's order, so the board stays stable.
        return list(pool.map(fetch_one, instruments))
