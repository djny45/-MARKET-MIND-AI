# Offline OHLCV CSV Research

This utility reads a **local CSV file** for educational analysis with the
existing SMC and TA-Lib research adapters. It is deliberately isolated from
TradingView, exchange APIs, broker APIs, and order execution.

## Required columns

`open`, `high`, `low`, and `close` are required (column names are
case-insensitive). `volume` is optional. Numeric fields must be finite;
OHLC bounds must be internally consistent; volume must be non-negative.

## Optional timestamp handling

Pass `timestamp_column="timestamp"` (or the actual column name) to parse
timestamps as UTC, reject duplicate timestamps, and sort rows chronologically.

```python
from app.offline_dataset import load_ohlcv_csv

df = load_ohlcv_csv("datasets/sample_ohlcv.csv", timestamp_column="timestamp")
```

## Important limitations

- The loader does not download market data or access external services.
- It does not produce trade recommendations, trading signals, or orders.
- Use only data you are authorized to use and check its source/licensing.
- Historical data may contain survivorship bias, gaps, and revisions.
- SMC swing labels can use future bars; do not treat them as point-in-time
  information or as evidence of predictive performance.
- This is an educational dataset validation utility, not financial advice.

## Run the research pipeline

```python
from app.offline_research_pipeline import run_offline_research

result = run_offline_research(
    "datasets/sample_ohlcv.csv",
    timestamp_column="timestamp",
    include_ta_lib=True,  # requires optional TA-Lib dependencies
    include_smc=True,     # requires optional SMC research dependencies
)
print(result["row_count"])
print(result["indicators"].keys())
```

Leave both indicator flags disabled to validate and load a dataset without installing optional indicator packages. Indicator output is historical annotation only; it is not a prediction or recommendation.
