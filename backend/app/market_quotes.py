"""Normalized, provider-neutral market quotes for the four research markets.

A quote is the smallest honest unit of market data: one symbol, one venue, one
price, one timestamp, and an explicit label saying *what kind* of observation
it is. This module defines that contract and the provenance rules that bind a
label to a source. It performs no network I/O and grants no provider access.

Provenance rules (deliberately stricter than the bar contract, because a quote
is presented to a human as "the price right now"):

* ``LIVE`` / ``DELAYED`` — the source must be present in the operator-attested
  set supplied by the caller. A public webpage is not attestation.
* ``SYNTHETIC`` — only the reserved ``synthetic-fixture`` source. A synthetic
  quote attributed to a real venue is a fabricated market price.
* ``HISTORICAL`` — any non-empty source; this is end-of-day or archived data.
* ``UNAVAILABLE`` — always allowed. Refusing to claim data is never a
  provenance violation and is the only honest label when a feed cannot be used.

Every quote carries ``source``, ``timestamp`` (event time) and ``retrieved_at``
(ingestion time) separately, and can report its own staleness against a
status-specific threshold.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .market_data import DataStatus

#: The four first-class research domains. Kept identical to
#: ``instruments._RAW_INSTRUMENTS`` market-group values on purpose.
MARKET_GROUPS: tuple[str, ...] = ("india", "us", "crypto", "forex")

#: Display label for each status. The UI renders these verbatim so an operator
#: can never read "live" out of a historical or synthetic observation.
STATUS_LABELS: dict[DataStatus, str] = {
    DataStatus.LIVE: "LIVE",
    DataStatus.DELAYED: "DELAYED",
    DataStatus.HISTORICAL: "HISTORICAL",
    DataStatus.SYNTHETIC: "SYNTHETIC",
    DataStatus.UNAVAILABLE: "UNAVAILABLE",
}

#: Maximum age in seconds before a quote of a given status is considered stale.
#: ``None`` means "age is not a meaningful test" (there is no observation, and a
#: historical quote is stale by definition of its own timestamp, not by age).
MAX_AGE_SECONDS: dict[DataStatus, int | None] = {
    DataStatus.LIVE: 60,
    DataStatus.DELAYED: 15 * 60,
    DataStatus.HISTORICAL: 7 * 24 * 3600,
    DataStatus.SYNTHETIC: 3600,
    DataStatus.UNAVAILABLE: None,
}

QUOTE_TYPES = frozenset({"indicative", "reference", "last_trade", "mid", "close"})

RESERVED_SYNTHETIC_SOURCE = "synthetic-fixture"


class QuoteType(str, Enum):
    INDICATIVE = "indicative"
    REFERENCE = "reference"
    LAST_TRADE = "last_trade"
    MID = "mid"
    CLOSE = "close"


def _aware(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


class MarketQuote(BaseModel):
    """One normalized observation for one instrument on one venue.

    ``bid``/``ask`` are optional and default to ``None``: a research terminal
    must never imply executable liquidity it does not have. When present they
    must not cross.
    """

    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=160)
    asset_class: str = Field(min_length=1, max_length=40)
    market_group: str | None = Field(default=None)
    exchange: str = Field(min_length=1, max_length=64)
    currency: str = Field(min_length=3, max_length=12)
    instrument_id: str | None = Field(default=None, max_length=96)

    last: float | None = Field(default=None, gt=0)
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    change_pct: float | None = None

    timestamp: datetime
    retrieved_at: datetime
    status: DataStatus
    source: str = Field(min_length=1, max_length=80)
    quote_type: QuoteType = QuoteType.INDICATIVE
    delay_seconds: int | None = Field(default=None, ge=0)
    reason: str | None = Field(default=None, max_length=400)

    #: IANA exchange timezone reported by the provider (e.g. Asia/Kolkata).
    #: ``timestamp`` is always normalized to UTC for exact comparison, but an
    #: operator also needs the exchange-local wall time to know which session
    #: an observation belongs to. Both are derived, never invented: if the
    #: provider did not declare a timezone, this stays ``None``.
    exchange_timezone: str | None = Field(default=None, max_length=64)

    #: Operator-attested sources. Not serialized: it is the rule set used to
    #: validate the claim, not part of the observation.
    attested_sources: frozenset[str] = Field(default_factory=frozenset, exclude=True)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be blank")
        return normalized

    @field_validator("market_group")
    @classmethod
    def validate_market_group(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if normalized not in MARKET_GROUPS:
            raise ValueError("market_group must be one of india, us, crypto, forex")
        return normalized

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("source cannot be blank")
        return normalized

    @field_validator("exchange_timezone")
    @classmethod
    def validate_exchange_timezone(cls, value: str | None) -> str | None:
        """Accept only a real IANA timezone; never a guessed offset string."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(normalized)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown IANA timezone: {normalized}") from exc
        return normalized

    @field_validator("timestamp", "retrieved_at")
    @classmethod
    def timestamps_must_be_aware(cls, value: datetime) -> datetime:
        if not _aware(value):
            raise ValueError("timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def retrieved_at_cannot_precede_event(self):
        if self.retrieved_at < self.timestamp:
            raise ValueError("retrieved_at cannot be earlier than the quote timestamp")
        return self

    @model_validator(mode="after")
    def bid_ask_must_not_cross(self):
        if self.bid is not None and self.ask is not None and self.bid > self.ask:
            raise ValueError("bid cannot exceed ask")
        return self

    @model_validator(mode="after")
    def provenance_label_must_match_source(self):
        """The core safety rule: a label is only as good as its attribution."""
        if self.status is DataStatus.UNAVAILABLE:
            # A last-known value may be retained for display, but an
            # unavailable observation must never imply executable liquidity.
            if self.bid is not None or self.ask is not None:
                raise ValueError(
                    "an unavailable quote cannot carry bid/ask; report the reason instead"
                )
            if not (self.reason and self.reason.strip()):
                raise ValueError("an unavailable quote must explain why")
            return self
        if self.status is not DataStatus.UNAVAILABLE and self.last is None:
            raise ValueError(f"a {self.status.value} quote requires a last price")
        if self.status in (DataStatus.LIVE, DataStatus.DELAYED):
            if self.source not in self.attested_sources:
                raise ValueError(
                    f"{self.status.value} quotes require an operator-attested source"
                )
        if self.status is DataStatus.SYNTHETIC and self.source != RESERVED_SYNTHETIC_SOURCE:
            raise ValueError(
                "synthetic quotes must use the reserved synthetic-fixture source, "
                "never a real venue or provider name"
            )
        return self

    @property
    def status_label(self) -> str:
        return STATUS_LABELS[self.status]

    def age_seconds(self, now: datetime | None = None) -> int:
        reference = now or datetime.now(tz=self.retrieved_at.tzinfo)
        return max(0, int((reference - self.timestamp).total_seconds()))

    def is_stale(self, now: datetime | None = None) -> bool:
        """Status-aware staleness.

        UNAVAILABLE has no observation to age, so it is never "stale" — it is
        simply not data. Callers must branch on the status, not on staleness.
        """
        threshold = MAX_AGE_SECONDS[self.status]
        if threshold is None:
            return False
        return self.age_seconds(now) > threshold

    def to_payload(self, now: datetime | None = None) -> dict[str, Any]:
        """JSON-safe dict including derived label and freshness fields."""
        payload = self.model_dump(mode="json", exclude={"attested_sources"})
        payload["status_label"] = self.status_label
        payload["age_seconds"] = self.age_seconds(now)
        payload["stale"] = self.is_stale(now)
        payload["max_age_seconds"] = MAX_AGE_SECONDS[self.status]
        # Derived exchange-local wall time. ``timestamp`` remains the canonical
        # UTC instant; this field answers "which session was this close in".
        if self.exchange_timezone:
            from zoneinfo import ZoneInfo

            payload["timestamp_exchange_local"] = self.timestamp.astimezone(
                ZoneInfo(self.exchange_timezone)
            ).isoformat()
        else:
            payload["timestamp_exchange_local"] = None
        return payload


def unavailable_quote(
    *,
    symbol: str,
    name: str,
    asset_class: str,
    market_group: str | None,
    exchange: str,
    currency: str,
    source: str,
    reason: str,
    timestamp: datetime,
    retrieved_at: datetime | None = None,
    instrument_id: str | None = None,
) -> MarketQuote:
    """Build an explicit "no data" quote instead of raising or inventing a price."""
    return MarketQuote(
        symbol=symbol, name=name, asset_class=asset_class,
        market_group=market_group, exchange=exchange, currency=currency,
        instrument_id=instrument_id, last=None,
        timestamp=timestamp, retrieved_at=retrieved_at or timestamp,
        status=DataStatus.UNAVAILABLE, source=source, reason=reason[:400],
    )


def quote_requests_are_valid(symbols: list[str], limit: int = 24) -> bool:
    return bool(symbols) and len(symbols) <= limit and all(s.strip() for s in symbols)


def freshness_legend() -> dict[str, Any]:
    """Machine-readable label legend so the UI never hardcodes semantics."""
    return {
        "labels": [
            {
                "status": status.value,
                "label": STATUS_LABELS[status],
                "max_age_seconds": MAX_AGE_SECONDS[status],
                "meaning": meaning,
            }
            for status, meaning in (
                (DataStatus.LIVE, "Operator-attested near-real-time observation."),
                (DataStatus.DELAYED, "Operator-attested feed with a known publication delay."),
                (DataStatus.HISTORICAL, "Archived or end-of-day observation; not a current price."),
                (DataStatus.SYNTHETIC, "Development fixture. Not a market observation."),
                (DataStatus.UNAVAILABLE, "No usable observation. No price is implied."),
            )
        ],
        "stale_rule": (
            "A quote is stale when its event age exceeds the status threshold. "
            "UNAVAILABLE quotes are never described as stale because there is "
            "nothing to age."
        ),
    }


def staleness_example() -> timedelta:  # pragma: no cover - documentation helper
    return timedelta(seconds=MAX_AGE_SECONDS[DataStatus.LIVE] or 60)
