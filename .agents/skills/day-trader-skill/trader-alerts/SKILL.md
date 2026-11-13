---
name: historical-data-observer
description: Inspect supplied historical market observations for timestamp gaps, stale metadata, and threshold crossings. Read-only quality reporting; no live alerts or execution.
---
# Historical data observer

## Purpose
Review user-supplied historical OHLCV or event data for completeness, chronology, and descriptive threshold crossings.

## Procedure
1. Confirm instrument, venue/source label, interval, timezone, retrieval timestamp, and dataset date range.
2. Check duplicate or missing timestamps, non-monotonic ordering, nulls, and inconsistent OHLC values.
3. Report any user-specified historical threshold crossings with the exact observation timestamp and source.
4. Distinguish observed values from derived calculations; never fill missing values silently.
5. State limitations, provider terms, and whether the input is synthetic, historical, or unverified.

## Boundaries
Do not monitor live markets, generate trade alerts, create stop/target instructions, or connect to a brokerage or order system. Do not recommend buying or selling.
