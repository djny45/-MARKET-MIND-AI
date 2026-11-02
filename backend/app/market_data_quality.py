"""Provider-neutral descriptive market-data quality checks.

Findings describe data completeness and provenance only. They are not trading
signals, price forecasts, or guarantees of provider accuracy.
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

from .market_data import MarketDataBatch, find_missing_candle_timestamps
from .data_quality import DataFreshnessReport, build_freshness_report


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"


class DataQualityFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)
    severity: FindingSeverity
    message: str = Field(min_length=1, max_length=300)
    count: int | None = Field(default=None, ge=0)


class MarketDataQualityReport(BaseModel):
    """Structured diagnostics; a clean report is not a guarantee of accuracy."""
    model_config = ConfigDict(extra="forbid")
    symbol: str
    interval: str
    source: str
    status: str
    bar_count: int = Field(ge=0)
    freshness: DataFreshnessReport
    missing_candle_timestamps: list[datetime]
    findings: list[DataQualityFinding]


def build_market_data_quality_report(
    batch: MarketDataBatch, *, now: datetime, freshness_threshold_seconds: float
) -> MarketDataQualityReport:
    """Combine freshness, candle-gap, empty-batch, and provenance diagnostics."""
    missing = find_missing_candle_timestamps(batch.bars, batch.interval)
    freshness = build_freshness_report(
        batch, now=now, threshold_seconds=freshness_threshold_seconds
    )
    findings: list[DataQualityFinding] = []

    if not batch.bars:
        findings.append(DataQualityFinding(
            code="EMPTY_BATCH", severity=FindingSeverity.WARNING,
            message="No candles were returned; completeness cannot be assessed.",
        ))
    if missing:
        findings.append(DataQualityFinding(
            code="CANDLE_GAPS", severity=FindingSeverity.WARNING,
            message="Expected candle timestamps are missing from this series.",
            count=len(missing),
        ))
    if freshness.stale is True:
        findings.append(DataQualityFinding(
            code="STALE_DATA", severity=FindingSeverity.WARNING,
            message="Newest candle exceeds the configured freshness threshold.",
        ))
    if batch.status.value == "synthetic":
        findings.append(DataQualityFinding(
            code="SYNTHETIC_DATA", severity=FindingSeverity.WARNING,
            message="Batch is synthetic fixture data, not market observations.",
        ))
    if batch.status.value == "historical":
        findings.append(DataQualityFinding(
            code="HISTORICAL_DATA", severity=FindingSeverity.INFO,
            message="Batch is historical data; it should not be presented as live.",
        ))
    if batch.warnings:
        findings.append(DataQualityFinding(
            code="PROVIDER_WARNINGS", severity=FindingSeverity.WARNING,
            message="Provider or adapter supplied warning text.",
            count=len(batch.warnings),
        ))

    return MarketDataQualityReport(
        symbol=batch.symbol, interval=batch.interval, source=batch.source,
        status=batch.status.value, bar_count=len(batch.bars),
        freshness=freshness, missing_candle_timestamps=missing,
        findings=findings,
    )
