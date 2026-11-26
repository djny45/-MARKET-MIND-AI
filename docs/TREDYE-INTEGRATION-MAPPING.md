# Tredye Research Integration — Feature-to-Existing-Module Mapping

Status: **pre-implementation audit**. The supplied
`tredye_reverse_engineering_report.pdf` was not present in the workspace; the
user supplied the report's capability description in text form. No Tredye
source code, assets, branding, analytics identifiers or undocumented endpoints
were copied. Findings are treated as research leads, not verified APIs.

## Audit scope

- `backend/app`: 268 files (134 Python modules)
- `frontend/src`: 16 files
- `.agents/skills/**`: existing skill pack (326 skills reported by `/api/skills` after PR #113 registration)
- `third_party/freqtrade`: vendored reference exchange classes, not wired in

## Mapping (Phase 14 acceptance table)

| Capability | Existing MARKET-MIND-AI module | Classification / action |
| --- | --- | --- |
| OKX provider | `.agents/skills/vibe-trading/skills/okx-market/` (docs/script only); `third_party/freqtrade/.../okx.py` (vendored, not imported) | **PARTIAL** — extend the existing `provider_adapters.py` registry with official public OKX V5 endpoints. Reuse `ProviderCapability`, `ProviderError`, `provider_policy.py` limiter, `market_data.py` contracts. |
| Coinbase provider | None | **MISSING** — add to the same adapter registry only for public reference/trade endpoints. A reference rate is never presented as an executable forex quote. |
| Bybit provider | `third_party/freqtrade/.../bybit.py` (vendored reference) | **PARTIAL** — implement a thin official-public-endpoint adapter in the existing registry; do not import vendored code. |
| Kraken provider | `third_party/freqtrade/.../kraken.py`, `krakenfutures.py` (vendored reference) | **PARTIAL** — same approach as Bybit. |
| Deribit provider / options | No adapter. `.agents/skills/vibe-trading/skills/options-advanced/` docs only; `indicators.py` realized vol only | **MISSING** — add official public options-ticker/index endpoints to the registry and a derived IV surface module if data supports it. Realized vol stays in `indicators.py`; no second analytics engine. |
| Hyperliquid provider | `third_party/freqtrade/.../hyperliquid.py` (vendored reference) | **PARTIAL** — thin official public-info adapter in the registry. |
| Fear & Greed | None | **MISSING** — alternative.me public endpoint under a new sentiment adapter in the registry, with source/timestamp provenance. |
| Gold analytics | `specialist_router.py:24` has a "gold" routing label only; no data adapter | **MISSING** — add a gold reference-price adapter to the same registry. Clearly distinguish spot/reference vs futures vs exchange-traded instruments. No synthetic gold prices. |
| Order-flow engine | `trade_flow.py` (`build_trade_flow_buckets`, buy/sell/CVD); `market_events.py` (`trade`, `quote`, `order_book_snapshot`, `open_interest`, `funding`); `market_event_quality.py`; API `/api/market-data/trade-flow`, `/api/market-data/events` | **PARTIAL** — extend `trade_flow.py` with notional, relative trade size, large-trade flags and market-flow summary. Reuse the existing event store; no new database or engine. |
| Order-book depth | `market_events.py` snapshot schema; `market_event_quality.py` crossed-book checks | **PARTIAL** — add a depth/imbalance computation that consumes existing snapshots; never interpret imbalance as directional proof. |
| Liquidation monitoring | No analytics; event schema has no liquidation type | **MISSING** — add a `liquidation` event type to `market_events.py` (extend, not replace) plus a summary in `trade_flow.py`, sourced from verified public feeds only. |
| Funding rate / OI | `market_events.py` already accepts `funding` and `open_interest` payloads; no derivation module | **PARTIAL** — add derivation/comparison helpers in the existing analytics module; preserve existing event contracts. |
| Options analytics | `indicators.py` realized vol; unregistered skill docs only | **PARTIAL/MISSING** — derive IV/Greeks in a new helper only if official Deribit data is actually fetched; reuse existing schemas for storage. |
| Indian broker connectors (FYERS/Upstox/Angel One/Dhan/Zerodha) | None. `docs/upstream-intelligence/...` mentions Dhan/Zerodha as upstream research notes only. Application auth modules are for platform users, not brokers. | **NOT PERMITTED / OUT OF SCOPE** — official broker APIs require credentials and approvals not present here. Implement a browser-side, credential-free *connection-status and sample-data labelling* surface only. No broker secrets to backend/agents/logs. No order execution. |
| Candlestick charts | `frontend/src/PriceChart.tsx` (lightweight-charts: candlestick, volume histogram, line, markers); `FourMarketChart.tsx`; `App.tsx` | **ALREADY IMPLEMENTED** — extend `PriceChart` with flow/liquidation/funding/OI overlays. Do **not** create another chart engine. |
| Market sentiment | `market_breadth.py`, `agent_collaboration.py`, `deep_analysis.py` (general summaries) | **PARTIAL** — feed Fear & Greed and flow indicators into the existing summary/report path, not a parallel engine. |
| Agent research skills | `workers.py` (550 profiles), `worker_registry.py`, `skill_catalog.py`, `research_skill_pack.py` (300 mm-skill-*), `worker_memory.py`, `analytical_agent_tasks.py`, `agent_network.py` | **ALREADY IMPLEMENTED** — reuse; extend task routing/skill references only. No new agents or duplicate skills. |
| Data provenance | `market_data.py`, `market_quotes.py`, `market_events.py`, `provider_health.py`, `provider_policy.py`, `data_licensing_gate.py`, `market_store.py` | **ALREADY IMPLEMENTED** — reuse every contract; new sources must pass the licensing gate and be labelled with source/event time/retrieval time/status. |
| Regulatory/disclosure docs | `README.md`, `SECURITY.md`, `docs/MARKET-COVERAGE.md`, `MARKET_DATA_LICENSING.md`, `DATA-LICENSING-GATE.md`, `FOUR-MARKET-PLATFORM.md` | **ALREADY IMPLEMENTED** — update these documents, do not create parallel ones. |

## Decisions

1. **One registry, one analytics engine, one chart.** All new data providers are
   added to `provider_adapters.py`/`four_market_bars.py`; all new flow analytics
   go into `trade_flow.py`/`market_events.py`; all overlays extend `PriceChart`.
2. **Licensing first.** `data_licensing_gate.py` blocks unlicensed live use.
   New public sources are registered as `pending_license_review` where
   appropriate and can never claim LIVE/DELAYED without attestation.
3. **Observed third-party endpoints** (`data.tredye.com/data/live.json`,
   `/api/cfno/okx`) are recorded as research leads only. No dependency on them.
4. **Brokers stay browser-side and credential-free** in this implementation;
   status labels and clearly-marked sample data only. No credential storage,
   no secrets in bundles/logs/agent memory, no execution.
5. **No duplicated docs.** Updates go into the existing platform/licensing docs.

## Files expected to change (all extensions)

- Extend: `backend/app/provider_adapters.py`, `backend/app/four_market_bars.py`,
  `backend/app/market_events.py`, `backend/app/trade_flow.py`,
  `backend/app/data_licensing_gate.py`, `frontend/src/PriceChart.tsx`,
  `frontend/src/FourMarketTerminal.tsx`, existing docs.
- Genuinely new (only where no existing module exists): a small
  `backend/app/market_intelligence.py` for cross-source research summaries and
  a `backend/app/exchange_intelligence_adapters.py` if venue endpoints cannot
  fit the existing adapter shape without distorting it. Each new file must be
  justified in the final report.

---

# Implementation Result (final)

The PDF was not available in the workspace. The operator supplied the report's
capability description in text form; that text was the only research reference.
No Tredye code, assets, branding, tracking/advertising scripts or undocumented
endpoints were copied or called.

## Reused (no duplicates created)

- **One provider architecture** — `provider_adapters.py` contracts,
  `market_quotes.py` `MarketQuote`, `market_data.py` `DataStatus`, and
  `provider_policy.py` limiter were reused by every new source.
- **One analytics engine** — `trade_flow.py` was extended (not replaced) with
  notional, relative size, large-trade detection, visual-dot payloads and
  liquidation summaries; `market_events.py` gained a `liquidation` event type.
- **One chart engine** — `PriceChart.tsx` was extended with trade-flow markers;
  no second chart library or component was added.
- **One agent ecosystem** — the existing 550-worker registry and 300-skill
  catalog were reused. Eight research topics map to existing allowlisted
  `mm-skill-*` entries; zero agents and zero skills were created.
- **One memory/provenance model** — findings use the existing `worker_memory`
  payload shape with source, event/retrieval timestamps, confidence and limits.
- **One licensing gate** — new public sources are `pending_license_review` and
  cannot claim LIVE/DELAYED; the two observed Tredye endpoints are on the
  unauthorized list.

## New files (only where nothing existing could be reused)

| File | Why existing modules were insufficient |
| --- | --- |
| `backend/app/exchange_intelligence.py` | No adapter existed for OKX, Coinbase, Bybit, Kraken, Deribit, Hyperliquid, Alternative.me or tokenized gold. It extends (does not replace) the provider registry and uses its contracts. |
| `backend/app/intelligence_research.py` | No routing existed from the new research topics to the existing skill catalog and evidence schema. |
| `frontend/src/IntelligencePanel.tsx` | No existing panel displayed the integrated venue/flow/sentiment/gold data with the required attribution and boundary disclosures. |
| Targeted tests | Existing suites did not cover the new sources, flow metrics or routing. |

## Verified exchange integrations (official public endpoints)

All returned HTTP 200 in bounded probes: OKX ticker/book/funding/OI, Coinbase
spot, Bybit ticker, Kraken ticker, Deribit index, Hyperliquid allMids,
Alternative.me Fear & Greed, CoinGecko PAX Gold. Six venue quotes rendered in a
real browser with `HISTORICAL` labels, sources and ages. OKX candles required
bar code `1D` (the report-style `1d` was rejected by the provider).

## Order flow

Trade notional, relative trade size, buy/sell flow, large-trade detection,
visual trade dots (green=buy, red=sell, amber=large/liquidation marker) and
liquidation summaries were added to the existing engine. Empty event stores
report `flow_direction: unavailable` and zero liquidations — no fabricated
activity. Depth is explicitly labelled as resting orders, not executed trades.

## Broker status

Not connected. `/api/brokers/status` reports all five brokers as
`not_connected`, `credential_storage: none`, `broker_execution: false`.
No broker credential path, token logging or order execution exists.

## Evidence

`docs/external-evidence/screenshots/exchange-intelligence-panel.png`,
`four-market-with-intelligence-full.png`,
`tredye-intelligence-evidence.json` (6 venue cards, 1 API call, 0 console errors).

## Test results

Backend full suite and frontend suites were re-run after all changes; see the
completion report for exact counts. No existing test was deleted; one licensing
manifest assertion was updated to reflect the honestly-expanded pending-review
list (a deliberate extension, not a regression).

### Test-isolation fix

A first batching implementation used an instance-level 60s cache in
`CoinGeckoCryptoAdapter`. That duplicated caching already provided by
`provider_policy` and leaked a real fetched price into offline tests that
patched the transport to fail. The redundant cache was removed; the constant
batched URL is cached only by the shared policy limiter. Offline tests are
green again, and one batched request still serves all crypto symbols.

### Exact test results (final run)

- Backend full suite: **1455 tests OK, 1 skipped**.
- Frontend Vitest: 24 files, 152 tests passed.
- Frontend `npm test`: 10 passed.
- `npm run typecheck:test`: clean.
- `npm run build`: production bundle created.
