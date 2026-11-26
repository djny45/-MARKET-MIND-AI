# Tredye-Inspired Analytics — Repository Integration Plan

**Status:** Research specification only. No new provider adapter or live feed is implemented by this document.

## Repository baseline inspected

The existing MARKET-MIND-AI main branch already contains reusable foundations:

- `backend/app/market_data.py`: provider-neutral OHLCV batch contract, timezone-aware bars, explicit LIVE / DELAYED / HISTORICAL / SYNTHETIC statuses, and source-attestation checks.
- `backend/app/market_data_validation.py`: structural payload validation; explicitly does not authenticate providers, certify licensing, or establish freshness.
- `backend/app/provider_health.py`: provider observations, freshness thresholds, health reporting and licensing-gate integration; performs no external calls.
- `backend/app/market_store.py`: SQLite OHLCV persistence retaining source, status and retrieval time.
- `backend/app/trade_flow.py`: descriptive buckets for imported historical trades; unknown side is not imputed and incomplete classification withholds CVD.
- `backend/app/instrument_master.py` and `backend/app/markets.py`: provider-neutral instrument reference catalogue and broad provider capability registry.
- `backend/app/data_licensing_gate.py` (existing dependency of provider health): licensing gate must be reviewed before enabling any feed.

These are strong starting points. Do not create parallel abstractions without demonstrating a concrete gap.

## Tredye report capabilities mapped to existing code

| Report capability | Existing foundation | Remaining work |
|---|---|---|
| Public exchange OHLCV | MarketDataBatch, validation, store | Authorized provider adapters, contract tests, runtime health checks |
| Trade stream / tape | Historical trade-flow aggregation | Normalized event contract, live stream lifecycle, replay and sequence-gap handling |
| Order-book depth | No complete normalized depth contract confirmed in this audit | Snapshot/delta schema, sequence validation, deterministic reconstruction and tests |
| Buy/sell imbalance | Historical trade-flow buckets | Windowed notional imbalance, side-confidence metadata and UI |
| Liquidations | No dedicated adapter confirmed in this audit | Provider-specific liquidation event adapters and normalized schema |
| Funding / open interest | No complete provider adapters confirmed in this audit | Derivatives adapters, unit normalization, timestamps and source attribution |
| Options / volatility | No complete options surface adapter confirmed in this audit | Instrument/expiry/strike schema, volatility summaries and provider capability checks |
| Gold | Commodity taxonomy exists | Explicit spot/reference/futures/tokenized-gold instrument definitions; unit/currency conversion |
| NSE F&O | India instruments and general market taxonomy exist | Licensed/authorized India data source review, instrument master validation, delayed/sample labels |
| Multi-venue comparison | Provider and instrument catalogues exist | Canonical symbol mapping, quote-currency normalization, contract-type checks and timestamp alignment |
| Agent research | Existing analytical agent runtime and skill catalog | Register skill, add research task templates, provenance-enforced output and end-to-end tests |

## Proposed normalized event contract

Add a separate event model rather than overloading OHLCV bars. Required fields:

- `schema_version`, `event_id`, `provider`, `venue`
- `instrument_id`, `provider_symbol`, `asset_class`, `quote_currency`, `unit`
- `event_type` (trade, book_snapshot, book_delta, liquidation, funding, open_interest, option_metric)
- `event_time` and `received_at` as timezone-aware UTC timestamps
- typed payload specific to event type
- `source_status` (live, delayed, historical, synthetic), `is_inferred`, `inference_method`
- `sequence_id` / `previous_sequence_id` where the venue supplies them
- `raw_payload_hash`, `schema_version`, `quality_flags`, `latency_ms`

Never manufacture missing event fields. Keep unknown trade side unknown. Keep raw source evidence separate from normalized records.

## Recommended implementation order

### Phase A — contracts and security
1. Audit existing licensing gate, provider health, streaming, market event and persistence modules.
2. Define typed event models and provider capability declarations.
3. Add fixtures and tests for malformed, stale, duplicated, out-of-order and timezone-naive events.
4. Add explicit secret-redaction tests and ensure provider credentials cannot enter browser bundles, logs, research exports or model prompts.

### Phase B — one provider at a time
1. Select one public provider and event family based on current official API documentation and terms.
2. Implement read-only adapter with bounded timeouts, retries, rate limiting and reconnect behavior.
3. Add mocked contract tests and a deterministic replay test.
4. Integrate provider health and data-quality reporting.
5. Enable only after licensing review and operator attestation; otherwise keep adapter disabled.

### Phase C — microstructure analytics
1. Order-book snapshot/delta reconstruction with sequence-gap reset.
2. Depth by basis-point band, spread and depth imbalance.
3. Trade notional imbalance with side-classification coverage.
4. Liquidation timeline and funding/open-interest time series.
5. Cross-venue comparisons only after symbol, unit, contract and time alignment.

### Phase D — India and gold
1. Verify source permissions and data licensing for NSE cash/index/F&O data.
2. Keep broker connections out of scope for execution; if user-authorized read-only broker data is ever considered, isolate credentials according to provider requirements and never expose them to backend/model/logs.
3. Represent gold spot, futures and tokenized instruments separately with explicit units and currencies.
4. Clearly label unavailable, delayed, historical and synthetic data.

### Phase E — agent and terminal integration
1. Register `.agents/skills/tredye-market-structure-research/SKILL.md` in the existing skill catalog if registration is required.
2. Add bounded research tasks for feed quality, order-flow, liquidations, derivatives positioning and cross-venue divergence.
3. Require each report to cite provider, venue, instrument, event time, retrieval time, method, confidence and quality status.
4. Add UI panels only after backend contracts and tests are stable.

## Acceptance criteria

- No fabricated live data; synthetic fixtures are unmistakably labelled.
- No claim of a connected/live provider until runtime health and source attestation pass.
- Every derived metric is reproducible from stored inputs and parameters.
- Order-book state resets safely on sequence gaps.
- Cross-venue comparisons reject incompatible symbols, currencies, units or contract types.
- Unknown trade side remains unknown; CVD is withheld when side coverage is incomplete.
- All event times are timezone-aware; UTC is canonical internally.
- Tests cover reconnects, rate limits, stale feeds, duplicate/out-of-order events, malformed payloads and provider outages.
- Secret scanning/redaction tests pass.
- Existing research-only / no-broker-execution boundary remains intact.
- CI, backend tests and frontend build pass before merge.

## Explicit non-goals

No broker order placement, private-key handling, transaction signing, automated live trading, market-making execution, or copying of Tredye proprietary code/assets. The supplied reverse-engineering report did not establish Tredye's proprietary aggregation formulas or complete internal implementation; those details must remain documented unknowns.
