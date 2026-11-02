# Market Data Freshness and Gap Checks

This repository provides descriptive checks for research-data pipelines. These checks do not produce trading signals, recommendations, or execution instructions.

## Freshness report

Use `build_freshness_report` from `backend.app.data_quality` with an explicit timezone-aware `now` value and a threshold in seconds.

The report includes:
- provider/source label and declared data status;
- retrieval timestamp from the batch;
- newest candle timestamp and calculated age;
- whether the age exceeds the supplied threshold.

If the batch has no bars, age and stale status remain unknown (`None`), not zero or fresh.

Example:

```python
from datetime import datetime, timezone
from app.data_quality import build_freshness_report

report = build_freshness_report(
    batch,
    now=datetime.now(timezone.utc),
    threshold_seconds=3600,
)
print(report.model_dump())
```

The caller supplies the clock deliberately so tests can use deterministic timestamps. A freshness threshold is application-specific and does not guarantee correctness, provider availability, or suitability for any financial decision.

## Missing candle timestamps

Use `find_missing_candle_timestamps` from `backend.app.market_data` to report absent candle-open timestamps for fixed-duration intervals (15m, 1h, 4h, 1d).

- Input bars must be chronological and unique.
- Timestamp spacing must align to the requested interval.
- The function reports missing timestamps only; it does not fill, interpolate, or fabricate data.
- Daily intervals are treated as 24-hour periods. Exchange-session calendars and market holidays are not modeled, so use this check carefully for markets with scheduled closures.

## Data status labels

`LIVE`, `DELAYED`, `HISTORICAL`, and `SYNTHETIC` are explicit labels carried by the data batch. A label is metadata supplied by the adapter, not independent verification. Synthetic fixtures must never be presented as real market observations.

## Running tests

From the backend directory, install dependencies from `requirements.txt`, then run:

```bash
python -m unittest discover -s tests -v
```

No external market-data API is required by these unit tests.
