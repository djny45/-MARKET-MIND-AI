# TA-Lib historical indicator research

MARKET-MIND-AI integrates the upstream **TA-Lib Python wrapper** as an optional dependency and Git submodule reference.

- Upstream: https://github.com/TA-Lib/ta-lib-python
- Submodule: `backend/app/vendor/ta-lib-python`
- Pinned upstream commit: `3e96c2191a871bc90d32c460c35f3ec6eca3b624`
- License: BSD 2-Clause (retain upstream LICENSE and attribution)
- Install optional dependencies from the backend directory:

```bash
python -m pip install -r requirements-ta-lib-research.txt
```

## Adapter

`app.ta_lib_research.analyze_historical_ohlcv(frame)` accepts a pandas DataFrame with OHLC columns and returns aligned arrays for RSI, MACD, ATR, SMA, EMA, and Bollinger Bands. TA-Lib lookback rows may be NaN by design.

This adapter uses only caller-supplied historical data. It does not download prices, provide financial advice, generate buy/sell orders, or connect to brokers/exchanges.

## Data-quality and evaluation cautions

- Ensure bars are chronological, timezone-aware at the ingestion boundary, and free of duplicate or missing intervals.
- Do not fill warm-up NaNs with future values.
- Evaluate indicators with point-in-time data and avoid look-ahead leakage, survivorship bias, and overfitting.
- Technical indicators are descriptive transformations, not reliable predictions or guarantees of outcomes.
- This is a research/education integration, not a live-trading system.

## Upstream source note

The Python wrapper is maintained by TA-Lib contributors. Its BSD 2-Clause license is available in the upstream repository. The TA-Lib C library is a separate upstream component; current upstream Python wheels may bundle the C library for supported platforms. See upstream installation documentation for platform/build requirements.
