# Liquidity and Market-Microstructure Research

This project uses liquidity-related data for historical, descriptive research only. These modules do not produce trading instructions, order requests, or broker actions.

## Research library status (corrected 2026-11-24)

An earlier version of this document claimed that `third_party/srl-python-indicators/`
had been vendored with seven indicator modules. **That directory does not exist in
this repository** and no such modules are imported. The claim is retracted rather
than treated as delivered work. The current `third_party/` tree contains only
inert reference copies of Camofox Browser, FinceptTerminal and Freqtrade.

The implemented liquidity analytics are native and deterministic:
`backend/app/liquidity_indicators.py` exposes the volume profile endpoint below,
and the core indicator endpoint covers the listed volume indicators.

## Liquidity analytics inventory

The API now exposes `POST /api/indicators/liquidity-profile` for an OHLCV-based approximate volume profile. Request fields are `high`, `low`, `close`, `volume`, optional `bins` (2–500, default 48), and `value_area_pct` (1–100, default 70). The response includes the volume-at-price histogram, POC, value-area high/low, local high/low volume nodes, and explicit approximation metadata. It does not claim to be a true trade-level profile. Regression tests cover normal, flat-price, and invalid-input cases.

The existing core volume-indicator endpoint already covers OBV, ADL, Chaikin Oscillator, CMF, MFI, Force Index, Ease of Movement, VPT, NVI, PVI, VWAP, relative volume, volume oscillator, volume ROC and volume SMA.

The implemented volume-profile endpoint provides an OHLCV approximation only; tick-level order-flow modules are **not** implemented. The broader liquidity data model should distinguish the following input classes:

| Input data | Historical measurements supported |
|---|---|
| OHLCV bars | Volume profile approximation, POC/VAH/VAL, VWAP, relative volume |
| Trade prints with aggressor side | Buy/sell volume, delta, cumulative delta, trade imbalance, footprint summaries |
| Best bid/ask quotes | Quoted spread, midpoint, microprice, top-of-book imbalance |
| Multi-level order-book snapshots | Depth by level, depth imbalance, liquidity concentration, order-flow imbalance |
| Open-interest history | OI change and OI/volume descriptive series |
| Funding-rate history | Funding level and historical change |
| Liquidation event history | Historical liquidation counts and notional by time/side, if supplied by a licensed source |

Important limitations:
- OHLCV bars do not contain actual bid/ask depth, aggressor-side trades, open interest, funding, or liquidation events. Those fields must never be fabricated or inferred as if observed.
- Buy/sell delta and footprint values require tick/trade data with reliable side classification. OHLCV-only estimates must be explicitly labelled as proxies.
- POC/VAH/VAL and volume-at-price values calculated from bars are approximations unless trade-level price/volume data is available.
- The upstream modules import optional plotting and numerical libraries. Dependencies are not installed globally by this import; isolate them in a dedicated environment before enabling any adapter.
- Do not run upstream examples that fetch external market data or start their GUI. The core application remains historical-research-only.

## Candidate open-source references reviewed

- https://github.com/srlcarlg/srl-python-indicators — Apache-2.0; reviewed but **not** vendored (no source tree in this repository).
- https://github.com/bfolkens/py-market-profile — Market Profile implementation; license metadata needs additional verification before copying or redistributing.
- https://github.com/flowdrivenml/market-data-stream-processor — interesting cross-venue order-book/trade/OI/funding/liquidation research prototype; no clear license was verified, so it was not copied.
- https://github.com/AbhayAbm/Limit-order-book — educational order-book simulator; excluded because it includes order matching and order-entry GUI, which are outside this project's scope.

## Integration policy

Keep imported code isolated under `third_party/`. Any future adapter must:
1. accept explicit historical datasets only;
2. validate timestamp ordering, duplicate events, units, and missing fields;
3. return provenance and data-quality metadata;
4. distinguish observed values from approximations;
5. avoid execution, order routing, or actionable trade recommendations.


## Historical trade flow analytics

The historical trade-flow endpoint aggregates imported trade events into deterministic UTC time buckets:

- `GET /api/market-data/trade-flow?instrument_id=india:nse:RELIANCE&bucket_seconds=60&limit=5000`
- Optional filters: `provider`, `venue`, `start`, `end`.
- Each bucket reports trade count, total volume, buy volume, sell volume, unknown-side volume, known-side delta and side-classification coverage.
- Cumulative volume delta (CVD) is returned only when every trade in the queried sample has a known buy/sell side. If any event has unknown side, CVD is withheld for the entire sample; unknown volume is not treated as zero.
- The response reports matching vs sampled events and whether the configured limit truncated the sample.

Side labels are supplied by the historical importer and are not independently verified. A "buy" or "sell" classification must be interpreted according to the source's documented aggressor/initiator convention. These are descriptive historical analytics, not live order flow, signals or execution inputs.
