"""Strict CSV importer for user-supplied historical OHLCV datasets."""
import csv
import io
import math
from datetime import datetime, timezone

from pydantic import ValidationError

from .market_data import DataStatus, MarketDataBatch, OHLCVBar

MAX_CSV_BYTES = 2_000_000
MAX_ROWS = 5_000
REQUIRED_COLUMNS = {"timestamp", "open", "high", "low", "close", "volume"}


def parse_historical_csv(
    csv_text: str,
    symbol: str,
    interval: str,
    source: str,
    retrieved_at: datetime | None = None,
) -> MarketDataBatch:
    """Parse a strict, header-based CSV into a validated historical batch.

    Timestamps must carry an explicit timezone. Invalid rows reject the entire
    import; timestamps are never guessed, shifted, or silently discarded.
    """
    if not isinstance(csv_text, str) or not csv_text.strip():
        raise ValueError("CSV content is required")
    if len(csv_text.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("CSV exceeds the 2 MB import limit")

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("CSV header row is required")
    normalized_headers = [(name or "").strip().lower() for name in reader.fieldnames]
    if len(normalized_headers) != len(set(normalized_headers)):
        raise ValueError("CSV contains duplicate column names after normalization")
    headers = set(normalized_headers)
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    # Normalize header names while preserving original row values.
    normalized_rows = []
    for row_number, row in enumerate(reader, start=2):
        if row_number > MAX_ROWS + 1:
            raise ValueError(f"CSV exceeds the {MAX_ROWS} row limit")
        if None in row or any(value is None for value in row.values()):
            raise ValueError(f"Invalid CSV row {row_number}: column count does not match header")
        normalized = {(key or "").strip().lower(): value for key, value in row.items()}
        try:
            timestamp = datetime.fromisoformat(
                normalized["timestamp"].strip().replace("Z", "+00:00")
            )
            values = {
                field: float(normalized[field])
                for field in ("open", "high", "low", "close", "volume")
            }
            if not all(math.isfinite(value) for value in values.values()):
                raise ValueError("OHLCV values must be finite numbers")
            normalized_rows.append(OHLCVBar(timestamp=timestamp, **values))
        except (ValueError, TypeError, KeyError, ValidationError) as exc:
            raise ValueError(f"Invalid CSV row {row_number}: {exc}") from exc

    if not normalized_rows:
        raise ValueError("CSV contains no data rows")

    # CSV uploads may arrive newest-first; normalize for downstream batch/store contracts.
    normalized_rows.sort(key=lambda bar: bar.timestamp)

    try:
        return MarketDataBatch(
            symbol=symbol,
            interval=interval,
            status=DataStatus.HISTORICAL,
            source=source,
            retrieved_at=retrieved_at or datetime.now(timezone.utc),
            bars=normalized_rows,
            warnings=[
                "User-supplied historical CSV; provider authenticity and licensing are not independently verified.",
                "Rows are validated and stored as supplied observations; missing intervals are not inferred.",
            ],
        )
    except ValidationError as exc:
        raise ValueError(f"CSV batch validation failed: {exc}") from exc
