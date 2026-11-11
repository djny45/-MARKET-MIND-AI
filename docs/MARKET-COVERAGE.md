# Market coverage and data-source strategy

## Instrument universe
The taxonomy covers equities, ETFs and funds, indices, spot and forward FX, sovereign and corporate fixed income, money markets, energy, metals, agriculture, listed futures and options, digital assets, and macroeconomic series.

Coverage is capability-based. No single provider is assumed to cover every instrument worldwide. Every adapter must document venues, instruments, fields, timestamp semantics, delay, rate limits, licensing, redistribution rights and gaps.

## Open/public source candidates

| Source | Useful data | Integration | Boundary |
|---|---|---|---|
| SEC EDGAR | US issuer filings, submissions, company facts | Official APIs and bulk datasets | Fair-access policy, user-agent and rate limits |
| ECB Data Portal | FX reference rates, yield curves, macro statistics | Official data API | Reference data is not executable FX pricing |
| Federal Reserve feeds | Central-bank releases | Official RSS | Publisher terms and cadence |
| FRED | US macro and financial time series | API adapter | API key and terms apply |
| EIA | Energy statistics | API adapter | API key, quotas and terms apply |
| Official exchange APIs | Quotes, trades, bars, depth | Venue adapters | Entitlements and redistribution restrictions |
| CoinGecko | Crypto metadata and market snapshots | Provider adapter | Rate limits and commercial terms vary |
| RSS/Atom publishers | Headlines and links | Configurable feed ingestion | Copyright, terms, robots and rate limits |

Open-source software and open data are different. Publicly reachable data is not automatically licensed for commercial reuse or redistribution. Store metadata, links and short excerpts only; verify source-specific rules before production display.

## News pipeline
1. Poll configured RSS/Atom feeds asynchronously with bounded concurrency.
2. Parse publisher, canonical URL, headline and publication timestamp.
3. Deduplicate on publisher plus URL.
4. Preserve publication and ingestion timestamps separately.
5. Normalize symbols/entities only with confidence and provenance.
6. Classify topic and asset class; preserve the original headline.
7. Publish metadata events to the pipeline.
8. Never treat sentiment as a verified market fact.

Default feeds are examples and may change or become unavailable. Review sources for your jurisdiction and use case.

## Canonical event contract
Every normalized event should carry provider, instrument ID, venue, event type, event time, received time, sequence where available, currency, price scale, delay status, entitlement and raw payload hash.

Stale, delayed, corrected, out-of-order or unlicensed data must be flagged. Never silently substitute one venue's price for another.


## Four primary market groups

The product organizes coverage into four top-level groups while retaining asset class as a separate dimension:

| Market group | Initial reference examples | Coverage caveat |
|---|---|---|
| India | NSE/BSE equities and indices; USDINR reference pair | Not a complete exchange master; exchange data requires appropriate entitlement |
| US | NASDAQ/NYSE-listed equities and ETFs; S&P 500 and Treasury yield references | Reference examples only; venue data rights vary |
| Crypto | BTC, ETH and SOL reference pairs | Venue-specific symbols and quote currencies must be mapped independently |
| Forex | EURUSD, USDJPY, GBPUSD, USDINR and other major pairs | OTC market; no single consolidated tape |

The API uses `market_group` for these domains and retains `market` for asset class. Example: `GET /api/instruments?market_group=india&market=equities`.

The current directory is a curated reference catalogue, not an exchange-supplied security master. It contains no live quotes and does not prove data availability. See [FOUR-MARKET-PLATFORM.md](FOUR-MARKET-PLATFORM.md) for canonical identity, event schemas and provider readiness.

## Stored-return heatmap

The private workspace exposes `GET /api/market-data/heatmap?interval=1d&limit=100`. It calculates a descriptive percentage change from the latest two distinct timestamps already stored for each symbol in the selected interval. If multiple sources have observations at one timestamp, the calculation selects the observation with the latest retrieval timestamp for that timestamp. Symbols with fewer than two distinct timestamps are returned with `status=insufficient_history` and no percentage change.

The result is limited to the locally stored symbol set and is ordered by absolute calculated change. It is not a live quote, a complete market-universe heatmap, a ranking of all exchange-listed instruments, or a trading signal. Source and data-status labels remain attached to each cell. The API's normal workspace authentication and CSRF/Origin controls apply.

## Stored heatmap query index

SQLite creates the additive `idx_market_bars_interval_timestamp` index on
`(interval, timestamp)` alongside the symbol-scoped lookup index. It supports
the heatmap's interval filter without changing stored rows or the schema
version. The index is created with `IF NOT EXISTS`, so existing databases
receive it automatically when the application opens the database. Its benefit
depends on data distribution and SQLite's query planner; confirm with
`EXPLAIN QUERY PLAN` and representative production-sized data before claiming
a measured speedup.

## Timestamp normalization

Stored OHLCV timestamps and retrieval timestamps are serialized in UTC before upsert. Because these values use one canonical UTC ISO-8601 representation, bar reads and heatmap ranking use exact timestamp text ordering/grouping rather than SQLite's lower-precision `julianday()` conversion; this preserves microsecond distinctions. Equivalent values such as `2026-01-01T05:30:00+05:30` and `2026-01-01T00:00:00+00:00` cannot create duplicate observations for new writes. This does not certify provider clock accuracy or repair arbitrary malformed legacy records.

Heatmap calculations also guard against floating-point overflow. If finite stored prices produce a non-finite percentage change (for example, an extreme ratio outside representable precision), the affected cell is returned with `status=numeric_overflow` and `change_pct=null`; the aggregate `numeric_overflow_count` reports these cells. Such a cell is not silently ranked as a valid return.
