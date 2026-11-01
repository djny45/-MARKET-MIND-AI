# Four-market platform implementation blueprint

## Product scope

MARKET-MIND-AI is being organized around four first-class research domains:

1. India: NSE and BSE equities and indices; listed derivatives, currency derivatives and fixed income only when authorized datasets are configured.
2. United States: NYSE, NASDAQ and other supported venues; equities, ETFs, indices, Treasury and corporate fixed-income reference data.
3. Crypto: venue-specific spot and derivatives instruments, historical bars, trades, quotes, order-book snapshots, funding and open-interest observations where available.
4. Forex: OTC currency pairs, cross rates, reference rates and timestamped bid/ask observations. OTC FX has no single consolidated exchange tape; provider and venue context must remain visible.

This is a coverage architecture, not a statement that all four markets currently have connected data feeds. The current provider status remains no live provider configured.

## Architecture rules

- One shared instrument master; never use a bare ticker as a globally unique key.
- Four market groups are separate from asset classes. For example, equities are an asset class while India and US are market groups.
- Preserve provider-native symbol, venue, currency, timezone, trading calendar and provider instrument ID.
- Keep observations venue-specific. Do not silently consolidate conflicting prices from different venues.
- Normalize event time and ingestion time separately, retaining original timezone/offset and provider sequence where supplied.
- Store prices, quantities, contract multipliers and rates with explicit units and precision.
- Tag every observation with source, entitlement, licence class, delay status, retrieval time and quality state.
- Treat missing coverage as missing, not as zero or an inferred value.
- All analytics must identify whether their inputs are observed, calculated, or approximate.

## Instrument reference API

The instrument reference endpoint is metadata-only:

- `GET /api/instruments?q=...&market=...&market_group=india`
- Supported market groups: `india`, `us`, `crypto`, `forex`.
- Existing `market` filter remains the asset-class filter, e.g. `equities`, `indices`, `fx`, `digital_assets`.
- Each catalogue row includes `instrument_id`, `symbol`, `name`, `market`, `market_group`, `instrument_type`, `venue`, `currency` and `metadata_status=reference_only`.
- The initial catalogue is a small curated reference set, not a complete exchange instrument master and not a quote source.

## Persistent instrument master

The SQLite-backed reference registry is available through:

- `GET /api/instrument-master?q=&market_group=india&market=equities&limit=50`
- `POST /api/instrument-master/identifiers`

Provider identifier registration body:

```json
{
  "instrument_id": "india:nse:RELIANCE",
  "provider": "provider-name",
  "venue": "NSE",
  "external_id": "provider-native-symbol",
  "identifier_type": "provider_symbol"
}
```

The curated reference catalogue is idempotently seeded into local SQLite storage. Provider identifiers are namespaced by provider, venue and external ID, so identical native symbols at different venues/providers do not collide. The API returns reference metadata only and explicitly reports that quotes are not included. The initial registry is not a complete exchange master and must be reconciled against authorized provider reference files before production use.

## Data domains and event contracts

### Common reference entities

- Instrument and instrument identifier mapping
- Venue and market calendar
- Currency and unit definitions
- Provider and licence/entitlement registry
- Corporate action and instrument lifecycle events

### Historical observations

| Dataset | Required fields | Main quality checks |
|---|---|---|
| OHLCV bars | instrument, venue, interval, event time, OHLC, volume, currency, source | OHLC envelope, duplicate bars, gaps, units, session alignment |
| Trades | instrument, venue, event time, sequence/trade ID, price, quantity, side classification and classification method | ordering, duplicate IDs, valid units, timestamp precision |
| Quotes | instrument, venue, event time, bid/ask prices and sizes | non-crossed quote checks, stale quote detection, sequence gaps |
| Order-book snapshots | instrument, venue, event time, sequence, side, price level, quantity, depth | sequence continuity, snapshot consistency, book reconstruction checks |
| Open interest | instrument, venue, contract, event time, quantity, unit | contract identity, publication time, revisions |
| Funding | instrument, venue, event time, rate, interval, settlement currency | interval normalization, sign convention, source |
| FX reference rates | base, quote, event date/time, rate type, rate, source | pair orientation, fixing time, reference-vs-tradable distinction |
| Fundamentals | issuer, security mapping, period, filing/publication time, currency, units, taxonomy | restatements, period alignment, currency and scale |

Do not calculate true CVD, footprint or historical depth from candle direction or OHLCV alone. They require appropriately classified trades or order-book observations. OTC FX prices must identify the contributing provider and quote type.

## Historical microstructure event store

The SQLite event store accepts imported historical observations through:

- `POST /api/market-data/events` — batch import of 1–1,000 events.
- `GET /api/market-data/events` — filter by canonical instrument ID, event type, provider, venue and UTC time range.

Supported event types:

| Event | Required payload | Validation |
|---|---|---|
| Trade | price, quantity, side | Positive price/quantity; side is buy, sell or unknown |
| Quote | bid/ask prices and sizes | Positive prices; bid cannot exceed ask |
| Order-book snapshot | bid and ask price/quantity levels | Non-empty bounded depth arrays; positive levels |
| Open interest | value, unit | Non-negative value and explicit unit |
| Funding | rate, interval, settlement currency | Explicit interval and settlement currency |
| FX rate | rate, base, quote, rate type | Positive rate, distinct currencies and explicit rate type |

Every event retains provider, venue, canonical instrument ID, event timestamp, received timestamp, optional sequence number, source status, payload SHA-256 and event ID. Timestamps must include a timezone and are normalized to UTC. Duplicate event IDs within the same provider/venue/instrument/event-type scope are ignored idempotently.

The importer does not authenticate provider claims, infer missing fields, repair sequence gaps, reconstruct order books from incomplete deltas or establish data completeness. The API is historical-import/query only; no exchange connection or live feed is enabled.

A diagnostic endpoint is also available:

- `GET /api/market-data/events/quality` — inspect stored event sequence continuity, duplicate/out-of-order sequence numbers, event/receive timestamp consistency and order-book snapshot level ordering/crossed-book conditions. It accepts the same scope and time filters as the event query and a limit up to 5,000.

Diagnostics operate on the returned sample only. Sequence gaps are conditional on provider sequence semantics; partial imports may produce apparent gaps. The endpoint flags anomalies for manual review and never repairs data or emits trading signals.

Example trade import:

```json
{
  "events": [{
    "event_id": "trade-0001",
    "instrument_id": "india:nse:RELIANCE",
    "event_type": "trade",
    "provider": "licensed-provider",
    "venue": "NSE",
    "event_time": "2026-10-30T09:15:00+05:30",
    "received_at": "2026-10-30T09:15:01+05:30",
    "status": "historical",
    "currency": "INR",
    "payload": {"price": 1450.0, "quantity": 10, "side": "unknown"}
  }]
}
```

## Provider and licensing controls

Provider adapters remain disabled until the project has recorded:
- documented API/feed specification;
- approved credentials and permitted use;
- display, non-display, storage and redistribution rights;
- venue and instrument coverage;
- rate limits, latency and retention constraints;
- timestamp, correction and outage semantics;
- test fixtures and adapter conformance tests.

Public accessibility is not equivalent to redistribution permission. NSE publishes distinct real-time, snapshot, end-of-day and historical products, and its data policy governs use and redistribution. Review the current agreements and tariffs before enabling Indian exchange data in any shared or commercial deployment:
- https://www.nse.in/static/nse-data-and-analytics/data-information-vending
- https://www.nseindia.com/static/market-data/nse-data-policy
- https://www.nse.in/static/market-data/real-time-data-subscription

## Implementation sequence

1. Instrument master and market-group filtering (initial reference catalogue now implemented).
2. Versioned database migrations for instruments, venues, providers and calendars.
3. Provider entitlement registry and adapter conformance contract.
4. Four-market historical OHLCV ingestion with venue-aware identity.
5. Corporate actions, sessions and reference-data normalization.
6. Historical trades and quotes.
7. Order-book snapshots and reconstruction with sequence validation.
8. Open interest, funding and FX reference series.
9. Cross-market charting, screening and analytics using explicit coverage metadata.
10. Authentication, authorization, audit and operational monitoring before shared/public deployment.

## Current implementation truth

- The instrument reference catalogue has a small sample of Indian, US, crypto and forex instruments.
- The existing SQLite bar store is still keyed by symbol, interval, timestamp and source. It is not yet a venue-aware global observation store.
- No live or delayed provider is configured.
- Synthetic fixtures remain explicitly labelled and must never be presented as market observations.
- No broker integration, order routing or automated execution is part of this platform.


## Cross-market agent collaboration

A deterministic research message bus allows specialist analytical modules in India, US, crypto and forex to exchange structured notes through one shared four-market mesh. Each market domain can publish to and read from the shared network; the topology exposes all 12 directed cross-market links.

API:
- `GET /api/agent-network` — market mesh topology, runtime and safety boundaries.
- `POST /api/agent-network/messages` — publish a structured note with agent ID, market group, topic, optional canonical instrument ID, source references, quality status and JSON payload.
- `GET /api/agent-network/messages?market_group=india&topic=macro&limit=100` — read shared notes, optionally filtered by market and topic. Omit market_group to read across all four markets.

Supported topics: macro, correlation, volatility, liquidity, breadth, event, data_quality, research_note and regime. Quality labels are caller-supplied metadata and are not independently authenticated. The message bus preserves source references and publication timestamps; it does not infer causal links, synchronize market sessions, validate conclusions or guarantee complete data.

**Important implementation boundary:** these are deterministic software research modules and a persistent message bus, not independent LLM agents. No model inference, live exchange feed, broker connection, order routing or trading execution is enabled. Data remains historical/manual-import or synthetic fixture data.


## Cross-market research roundtable

The shared message bus can be assembled into a deterministic collaboration brief:

- `GET /api/agent-network/brief?limit=500` — summarize shared messages from all market groups.
- Optional `topic` filter limits the brief to one supported research topic.
- The response reports message counts by market and quality label, participating markets, topic counts, and comparable structured findings.
- To make a finding comparable, a message payload may include scalar `finding_key`, `finding_value` and optional `unit` fields. Only matching topic/key/unit groups are compared.
- Different supplied values are surfaced for analyst review. Matching values are described as agreement only, never proof of causality or statistical consensus.

This is a read-only aggregation of existing research notes. It does not autonomously dispatch agents, load an AI model, create market data, synchronize sessions, or produce trade signals. Each market domain can publish and read the shared bus; the brief gives analysts a compact cross-market view of those conversations.
