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
