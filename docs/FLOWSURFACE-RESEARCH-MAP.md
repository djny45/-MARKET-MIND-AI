# Flowsurface Research Integration Map

This document maps useful Flowsurface components to the existing MARKET-MIND-AI historical research application. It does not embed Flowsurface's desktop UI or execute its indicator DSL.

## Upstream snapshot

- Repository: https://github.com/flowsurface-rs/flowsurface
- Pinned commit: `50c06caac0cf7ce9c3bcaabcf99fbd4e4e0f6746`
- Local source archive: `third_party/Flowsurface/`
- Import scope and licence notes: `third_party/Flowsurface/IMPORT-NOTES.md`

## Useful capabilities identified

| Flowsurface component | Research value | Required source data |
|---|---|---|
| K-line chart and volume profile | Historical price/volume visualization | OHLCV; trade-level VAP is more accurate |
| Footprint chart | Bid/ask traded volume by price | Trades with aggressor-side classification |
| Cumulative Volume Delta (CVD) | Cumulative signed traded volume | Buy/sell quantities or classified trades |
| Time & Sales | Trade event inspection | Timestamped trade prints |
| Order-book ladder and depth heatmap | Resting liquidity by price level | Timestamped L2 snapshots or incremental book events |
| Open Interest indicator | OI level and change | Historical OI observations |
| Anchored VWAP | Anchored volume-weighted price | OHLCV approximation or trade prints |
| TPO profile | Time-at-price distribution | Intraday bars or trade events |

## Existing MARKET-MIND-AI functionality

- OHLCV history store and CSV import.
- Historical data quality, source comparison, lineage and evidence exports.
- Volume indicators endpoint: `POST /api/indicators/volume`.
- Approximate OHLCV volume profile endpoint: `POST /api/indicators/liquidity-profile`.
- React research dashboard already renders Volume Intelligence and Liquidity Profile panels.

## Data-readiness rules before implementing new metrics

1. CVD and footprint values require observed buy/sell volume or trade aggressor-side classification. Do not infer them from candle colour.
2. Order-book depth and heatmaps require timestamped L2 snapshots or a correctly reconstructed incremental order book. Do not derive them from OHLCV.
3. Spread and microprice require synchronized best bid and ask quotes.
4. Open-interest change requires a source that actually publishes historical OI.
5. Funding and liquidation metrics require timestamped source observations with units, venue, instrument and provenance.
6. Every output must distinguish observed values, derived values and approximations, and expose missing-data coverage.

## Licensing boundary

The Flowsurface root application and bundled `.ind` indicator collection are GPL-3.0-or-later; its indicator engine is Apache-2.0; its exchange crate is MIT. The relevant upstream notices remain in the source archive. Do not copy GPL application or bundled-indicator code into the existing backend/frontend or combine it into a distributable product without reviewing GPL obligations. The current integration uses the source archive as an isolated reference.

## Next engineering milestone

Introduce a separate historical market-microstructure data schema (trades, best quotes, L2 snapshots, OI, funding and liquidation events), with strict provenance and validation. Only after a real historical dataset or licensed provider is available should CVD, footprint, depth imbalance, spread, microprice, OI and liquidation analytics be exposed in the dashboard.
