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
- Counts grouped by source and observation status, plus available retrieval timestamps.\n- Relative volume against an inclusive trailing window, return volatility per observation, descriptive volatility bands, and historical close-to-close maximum drawdown.\n- Optional cross-asset Pearson correlation using exact timestamp matches between close-to-close return series, including paired sample counts.\n- Historical price-level clusters formed from repeated confirmed swing highs and lows, with configurable percentage tolerance and minimum touch count.
- Coverage summary identifying intervals with insufficient stored bars.

## Historical price-level clusters\n\nEach timeframe deep report groups confirmed swing highs and swing lows into separate historical price clusters. The default tolerance is 0.5% and the minimum cluster size is two confirmed pivots. Clusters report their mean, observed price range, touch count, timestamps and indices. These are historical price concentrations, not guaranteed support/resistance or future targets. The swing detector excludes pivots without the required right-side confirmation bars.\n\n## Cross-asset comparison\n\nAdd `--correlate-symbols ETHUSD,SOLUSD` to a deep single-timeframe command. The primary `--symbol` is included automatically; at most 12 total symbols are accepted. Correlation uses exact timestamp intersections and the first selected interval in multi-timeframe mode. Missing pairs or constant series produce null values rather than invented estimates.\n\n## Interpretation and limits

Correlation is historical co-movement, not causation; it can vary across samples and does not establish diversification or forecast future relationships.\n\nVolume and volatility diagnostics are descriptive. Relative volume uses the latest bar divided by the inclusive trailing average; volatility is reported per observation without annualization; drawdown uses closing prices only. Volatility bands use fixed thresholds and are not calibrated across asset classes.\n\nThe quality status means only that the implemented structural checks did or did not find issues. It does not certify data accuracy, source authenticity, licensing, or completeness. Retrieval timestamps are shown, but no freshness verdict is inferred. Missing bars are not labelled as errors because exchange calendars, trading sessions and provider schedules differ.

This is a historical descriptive research feature. It does not produce forecasts, directional signals, investment recommendations, or orders. Execution remains disabled.
