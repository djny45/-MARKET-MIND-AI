"""Provider-neutral descriptive checks for historical market-data batches."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .market_data import DataStatus, MarketDataBatch


class DataFreshnessReport(BaseModel):
    """Freshness metadata only; not a quality guarantee or trading signal."""
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=1, max_length=80)
    status: DataStatus
    retrieved_at: datetime
    newest_bar_at: datetime | None = None
    age_seconds: float | None = Field(default=None, ge=0)
    stale: bool | None = None
    threshold_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_consistency(self):
        for field in ("retrieved_at", "newest_bar_at"):
            value = getattr(self, field)
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"{field} must include a timezone")
        if self.age_seconds is None and self.stale is not None:
            raise ValueError("stale must be omitted when age is unknown")
        if self.age_seconds is not None:
            if self.stale is None:
                raise ValueError("stale must be provided when age is known")
            if self.stale != (self.age_seconds > self.threshold_seconds):
                raise ValueError("stale must match age and threshold")
        return self


def build_freshness_report(
    batch: MarketDataBatch, *, now: datetime, threshold_seconds: float
) -> DataFreshnessReport:
    """Compute newest-bar age using explicit caller time (no implicit clock access)."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must include a timezone")
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be positive")
    newest = batch.bars[-1].timestamp if batch.bars else None
    age = None if newest is None else (now - newest).total_seconds()
    if age is not None and age < 0:
        raise ValueError("now cannot precede newest bar")
    return DataFreshnessReport(
        source=batch.source,
        status=batch.status,
        retrieved_at=batch.retrieved_at,
        newest_bar_at=newest,
        age_seconds=age,
        stale=None if age is None else age > threshold_seconds,
        threshold_seconds=threshold_seconds,
    )
