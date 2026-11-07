---
name: yahoo-finance-historical-data
description: Fetch and validate Yahoo Finance chart history for research only.
---

# Yahoo Finance historical-data skill

Use MARKET-MIND-AI's `YahooFinanceAdapter` from `backend/app/yahoo_finance_adapter.py` to request normalized OHLCV bars.

## Workflow
1. Confirm symbol and supported interval: `15m`, `1h`, `4h`, or `1d`.
2. Call the adapter with a bounded limit (1–5000).
3. Preserve source, retrieval timestamp, data status, and warnings in the report.
4. Check gaps, timestamps, symbol mapping, and stale-data risk before analysis.
5. Distinguish historical data from delayed/live quotes.

## Limitations
- Best-effort Yahoo Finance chart endpoint; availability, throttling, terms, and response formats may change.
- This is not an official guaranteed API or a real-time feed.
- `4h` requests Yahoo hourly history and aggregates only groups of four consecutive hourly candles within a continuous session segment. Groups are anchored to the first hourly timestamp (not UTC midnight); gaps split segments, and incomplete groups are discarded. This is a research approximation of session-aligned 4h bars, not Yahoo-native 4h data.
- Do not use the adapter as broker execution data, nor infer guaranteed prices or returns.
- Never hide provider errors or freshness warnings.

## Upstream reference
This capability is inspired by the Yahoo Finance historical-data loader pattern in HKUDS/Vibe-Trading. This is a new adapter implementation, not a verbatim copy of upstream source.
