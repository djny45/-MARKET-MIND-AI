# Stooq Historical Market Data

## Purpose
Use the MARKET-MIND-AI Stooq adapter to retrieve daily OHLCV bars for historical market research, charting, and reproducible offline analysis.

## Input and output
- Python adapter: `app.stooq_adapter.StooqAdapter`
- Supported interval: daily only (`1d`).
- Symbols must use Stooq conventions (for example, US equities commonly use `aapl.us`).
- Optional API key: configure `STOOQ_API_KEY` when the provider requires it. Never commit credentials.
- Output is normalized to `MarketDataBatch`, including provider name, retrieval timestamp, historical status, and warnings.

## Quality and access rules
- Treat the provider as best-effort. Access requirements, rate limits, symbol coverage, and response format can change.
- Detect quota messages, API-key prompts, and HTML challenge pages instead of interpreting them as CSV.
- Daily dates are normalized to UTC midnight for the project contract; this is a date label, not an intraday timestamp.
- Never fill missing provider rows with synthetic data or silently claim realtime freshness.
- Check source terms before caching, storing, redistributing, or republishing Stooq data.
- Do not use this adapter for live trading, broker routing, execution decisions, or financial recommendations.
- Compare historical data with another source where accuracy matters; flag gaps and discrepancies for human review.

## Inspired-by attribution
This skill is newly authored for MARKET-MIND-AI. It follows the general public CSV-loader integration pattern discussed in HKUDS/Vibe-Trading's Stooq loader, without copying its implementation. See upstream: https://github.com/HKUDS/Vibe-Trading/blob/main/agent/backtest/loaders/stooq_loader.py
