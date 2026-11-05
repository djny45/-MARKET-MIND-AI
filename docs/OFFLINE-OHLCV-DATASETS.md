# Offline OHLCV and Webhook Payload Research

This repository's research utilities operate on local files and fabricated
examples. They are isolated from TradingView, exchange APIs, broker APIs,
external notification services, and order execution.

## Offline OHLCV CSV research

Required columns are open, high, low, and close (case-insensitive).
Volume is optional. Numeric values must be finite, OHLC bounds consistent,
and volume non-negative. Timestamp parsing (when enabled) normalizes to UTC,
rejects duplicates/missing timestamps, and sorts chronologically. Numeric epoch
timestamps are rejected as ambiguous; convert them to ISO-8601 timestamps with
an explicit timezone first.

Run the synthetic sample validation demo from the repository root:

```bash
python backend/examples/run_synthetic_offline_demo.py
```

The bundled CSV is fabricated test data, not actual market history.

## Offline webhook payload lab

A safe local parser demonstration inspired by webhook event formats is provided.
It accepts only inert sample/synthetic/local events and rejects unknown fields,
including credentials. It does **not** open an HTTP port, receive external
webhooks, forward messages to Telegram/Discord/Slack, or connect to TradingView.

Run it from the repository root:

```bash
python backend/examples/webhook_payload_lab_demo.py
```

The accepted sample schema is limited to:
- event_id, source, and message (required)
- symbol, timeframe, and created_at (optional)

## Research pipeline

The bundled dataset is located at `backend/examples/synthetic_ohlcv.csv`.
From the repository root, run this example with the backend directory on
Python's import path:

```bash
PYTHONPATH=backend python - <<'PY'
from app.offline_research_pipeline import run_offline_research

result = run_offline_research(
    "backend/examples/synthetic_ohlcv.csv",
    timestamp_column="timestamp",
    include_ta_lib=False,
    include_smc=False,
)
print(result["row_count"])
PY
```

Optional TA-Lib and SMC adapters provide historical annotations only, not
predictions, recommendations, or trade signals. Indicator calculations require
a timestamp column so bars are ordered chronologically. SMC swing labels can
use future bars; avoid look-ahead bias.

## Limitations and data responsibility

- No network calls, trading signals, orders, or external notifications.
- Use only data you are authorized to use and check its license.
- Historical datasets can contain gaps, revisions, and survivorship bias.
- These examples are for educational software testing, not financial advice.

## Local CSV inspector

For a lightweight CSV header and row-count check without loading indicator
libraries, run:

```bash
python backend/examples/local_csv_inspector.py path/to/local.csv
```

This reports the file name, file size in bytes, row count, and column names.
It rejects empty or duplicate headers (after trimming whitespace). It reads the
file locally and does not modify it or access network services.

## Offline dataset report generator

Generate a descriptive JSON report from a local OHLCV file:

```bash
python backend/examples/offline_dataset_report.py backend/examples/synthetic_ohlcv.csv
python backend/examples/offline_dataset_report.py backend/examples/synthetic_ohlcv.csv --timestamp-column timestamp --output report.json
```

The report includes file metadata, row count, column names, min/max/mean
statistics for OHLCV columns, and validation summaries. If a timestamp column
is provided, it also reports the UTC time range after chronological sorting.
This is descriptive historical analysis only; it does not create forecasts,
trading signals, or orders.
