# Market-data quality diagnostics

The backend can combine candle-gap and freshness checks into a structured,
provider-independent report.

## Example

Run from the `backend/` directory:

```python
from datetime import datetime, timezone

from app.market_data import MarketDataBatch
from app.market_data_quality import build_market_data_quality_report

report = build_market_data_quality_report(
    batch,
    now=datetime.now(timezone.utc),
    freshness_threshold_seconds=3600,
)
print(report.model_dump(mode="json"))
```

Use a timezone-aware `now` supplied by the caller. This makes tests
reproducible and avoids hidden clock assumptions.

## Finding codes

| Code | Meaning |
|---|---|
| `EMPTY_BATCH` | No candles were returned |
| `CANDLE_GAPS` | Expected candle timestamps are absent |
| `STALE_DATA` | Newest candle is older than the configured threshold |
| `SYNTHETIC_DATA` | Dataset is a development fixture, not market observations |
| `HISTORICAL_DATA` | Dataset is historical and must not be labeled live |
| `PROVIDER_WARNINGS` | Adapter supplied warning messages |

The report is descriptive. It does not assess market direction, recommend
transactions, or guarantee provider accuracy. A report with no findings is
not proof that data is complete, correct, or suitable for any particular use.

## Interval assumptions

Candle-gap detection assumes fixed-duration intervals (15m, 1h, 4h, 1d) and
candle-open timestamps. The 1d interval is treated as 24 hours; exchange-session
calendars, holidays, and daylight/session rules require provider-specific
calendar logic and are outside this helper's scope.

## Tests

From the `backend/` directory:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```
