"""Provider-neutral market-data contracts and explicitly synthetic fixtures.

Fixtures are for UI and pipeline development only; they are not historical or live prices.
"""
from datetime import datetime, timezone
import math
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class DataStatus(str, Enum):
    LIVE = "live"
    DELAYED = "delayed"
    HISTORICAL = "historical"
    SYNTHETIC = "synthetic"


class OHLCVBar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    adjusted_close: float | None = Field(default=None, gt=0)

    @field_validator("open", "high", "low", "close", "volume", "adjusted_close", mode="before")
    @classmethod
    def numeric_values_must_be_finite(cls, value, info):
        # Run before Field(gt/ge) so NaN and infinity get the intended error.
        try:
            number = float(value)
        except (TypeError, ValueError):
            return value
        if not math.isfinite(number):
            raise ValueError(f"{info.field_name} must be finite")
        return value

    @model_validator(mode="after")
    def validate_numeric_values_are_finite(self):
        for field_name in ("open", "high", "low", "close", "volume", "adjusted_close"):
            value = getattr(self, field_name)
            # adjusted_close is optional; validate only when the provider supplies it.
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{field_name} must be finite")
        return self

    @model_validator(mode="after")
    def validate_ohlc_envelope(self):
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("high must be at least open, low, and close")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be at most open, high, and close")
        return self

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @field_validator("high")
    @classmethod
    def high_must_cover_ohlc(cls, value: float, info):
        low = info.data.get("low")
        open_value = info.data.get("open")
        close = info.data.get("close")
        if low is not None and value < low:
            raise ValueError("high cannot be below low")
        if open_value is not None and value < open_value:
            raise ValueError("high cannot be below open")
        if close is not None and value < close:
            raise ValueError("high cannot be below close")
        return value

    @field_validator("low")
    @classmethod
    def low_must_cover_ohlc(cls, value: float, info):
        open_value = info.data.get("open")
        close = info.data.get("close")
        if open_value is not None and value > open_value:
            raise ValueError("low cannot be above open")
        if close is not None and value > close:
            raise ValueError("low cannot be above close")
        return value


class MarketDataBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    symbol: str = Field(min_length=1, max_length=32)
    interval: str = Field(min_length=1, max_length=16)
    status: DataStatus
    source: str = Field(min_length=1, max_length=80)
    retrieved_at: datetime
    bars: list[OHLCVBar] = Field(max_length=5000)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("symbol cannot be blank")
        return normalized

    @field_validator("interval")
    @classmethod
    def validate_interval(cls, value: str) -> str:
        if value not in {"15m", "1h", "4h", "1d"}:
            raise ValueError("interval must be one of 15m, 1h, 4h, 1d")
        return value

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source cannot be blank")
        return normalized

    @model_validator(mode="after")
    def bars_cannot_postdate_retrieval(self):
        future_bars = [bar.timestamp for bar in self.bars if bar.timestamp > self.retrieved_at]
        if future_bars:
            raise ValueError("bar timestamps cannot be later than retrieved_at")
        return self

    @model_validator(mode="after")
    def validate_bar_timestamp_order(self):
        timestamps = [bar.timestamp for bar in self.bars]
        if len(timestamps) != len(set(timestamps)):
            raise ValueError("batch contains duplicate bar timestamps")
        if timestamps != sorted(timestamps):
            raise ValueError("batch bars must be ordered by ascending timestamp")
        return self

    @field_validator("retrieved_at")
    @classmethod
    def retrieval_time_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        return value

    @field_validator("warnings")
    @classmethod
    def warning_messages_must_be_nonblank(cls, value: list[str]) -> list[str]:
        normalized = [warning.strip() for warning in value]
        if any(not warning for warning in normalized):
            raise ValueError("warnings must not contain blank messages")
        return normalized


class MarketDataAdapter(Protocol):
    """Contract implemented by authorized market-data providers."""

    name: str

    async def get_bars(self, symbol: str, interval: str, limit: int) -> MarketDataBatch:
        """Return normalized bars with source and freshness metadata."""
        ...


class SyntheticFixtureAdapter:
    """Deterministic non-market fixture. Never represents a real quote."""

    name = "synthetic-fixture"

    async def get_bars(self, symbol: str, interval: str = "1d", limit: int = 5) -> MarketDataBatch:
        if not symbol.strip():
            raise ValueError("symbol is required")
        if interval not in {"1d", "1h", "15m"}:
            raise ValueError("unsupported fixture interval")
        if limit < 1 or limit > 5:
            raise ValueError("fixture limit must be between 1 and 5")
        base = [
            (100.0, 103.0, 99.0, 102.0, 1200.0),
            (102.0, 104.0, 101.0, 103.0, 1350.0),
            (103.0, 105.0, 100.0, 101.0, 1420.0),
            (101.0, 104.0, 100.5, 103.5, 1510.0),
            (103.5, 106.0, 102.0, 105.0, 1600.0),
        ]
        bars = []
        for index, values in enumerate(base[-limit:]):
            bars.append(OHLCVBar(
                timestamp=datetime(2026, 1, 1 + index, tzinfo=timezone.utc),
                open=values[0], high=values[1], low=values[2],
                close=values[3], volume=values[4],
            ))
        return MarketDataBatch(
            symbol=symbol.strip().upper(), interval=interval,
            status=DataStatus.SYNTHETIC, source=self.name,
            retrieved_at=datetime.now(timezone.utc), bars=bars,
            warnings=["Synthetic development fixture only; not live, delayed, or historical market data."],
        )
