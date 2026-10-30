# Deep Analysis Guide

The terminal's `--deep` option combines existing deterministic chart research with explicit stored-bar quality diagnostics.

## Commands

Run from `backend/`:

```bash
PYTHONPATH=. python terminal_chart_report.py --symbol BTCUSD --mode single --interval 1h --limit 500 --deep
PYTHONPATH=. python terminal_chart_report.py --symbol BTCUSD --mode multi --intervals 15m,1h,4h,1d --limit 500 --deep
```

Supported intervals are `15m`, `1h`, `4h`, and `1d`. Multi-timeframe output only compares intervals with enough stored observations; it never interpolates missing bars.

## Included research

- Moving-average regime, RSI, MACD, Bollinger Bands and ATR.
- Recent range references, candle-geometry labels and confirmed swing points.
- Per-timeframe quality checks for duplicate timestamps, invalid timestamps, non-increasing timestamps, inconsistent OHLC values, negative volume and missing required fields.
- Counts grouped by source and observation status, plus available retrieval timestamps.
- Coverage summary identifying intervals with insufficient stored bars.

## Interpretation and limits

The quality status means only that the implemented structural checks did or did not find issues. It does not certify data accuracy, source authenticity, licensing, or completeness. Retrieval timestamps are shown, but no freshness verdict is inferred. Missing bars are not labelled as errors because exchange calendars, trading sessions and provider schedules differ.

This is a historical descriptive research feature. It does not produce forecasts, directional signals, investment recommendations, or orders. Execution remains disabled.
