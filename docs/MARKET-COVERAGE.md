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

## Exchange intelligence extension (Tredye research findings)

A research report describing Tredye was studied as an architectural reference;
its PDF was not available in this workspace, so only the capability description
supplied by the operator was used. No Tredye source code, assets, branding,
analytics identifiers, advertising scripts or undocumented endpoints were
copied. The observed third-party endpoints (`data.tredye.com/data/live.json`
and `/api/cfno/okx`) are recorded as research leads in
[TREDYE-INTEGRATION-MAPPING.md](TREDYE-INTEGRATION-MAPPING.md) and are **never
called**.

Official public endpoints from OKX, Coinbase, Bybit, Kraken, Deribit,
Hyperliquid, Alternative.me and CoinGecko (PAX Gold) are integrated through the
**existing** provider registry and policy limiter in
`backend/app/exchange_intelligence.py`. They are labelled `HISTORICAL`, carry
source/event/retrieval timestamps and pass through the existing licensing gate
as `pending_license_review`. No source is attested, so none may claim LIVE or
DELAYED. Failures become `UNAVAILABLE` with a reason; no price is fabricated.

Specific boundaries:

- Coinbase USD/INR is a **reference rate**, not an executable forex quote.
- PAX Gold is a **tokenized, exchange-traded instrument**, not spot gold or a
  gold futures contract. Missing data is reported as `UNAVAILABLE`, never
  synthesized.
- OKX order-book depth represents **displayed resting orders**, not executed
  trades. Imbalance is descriptive and is not evidence of future direction.
- Funding, open interest and Fear & Greed are observations/indicators with
  attribution; none is a trading signal.
- Indian broker connectors (FYERS, Upstox, Angel One, Dhan, Zerodha Kite) are
  **not enabled**. Official APIs require credentials and approvals not present
  here. `/api/brokers/status` reports `not_connected` and sample/historical
  labelling only. No broker credential is accepted by the backend, stored in
  agent memory, logged, or included in a frontend bundle. Broker order
  execution, transaction signing and autonomous live trading remain disabled.
