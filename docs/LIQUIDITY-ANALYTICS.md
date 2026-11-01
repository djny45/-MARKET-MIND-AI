# Liquidity and Market-Microstructure Research

This project uses liquidity-related data for historical, descriptive research only. These modules do not produce trading instructions, order requests, or broker actions.

## Imported open-source research library

Vendored source: `third_party/srl-python-indicators/`

- Upstream: https://github.com/srlcarlg/srl-python-indicators
- License: Apache-2.0 (upstream LICENSE is included)
- Upstream branch copied: `master`
- Scope copied: Python indicator modules and their `models_utils` support files, README, and license.
- Excluded: upstream market-data Parquet files, notebooks, generated plots, and test datasets.
- The code is vendored for inspection and future isolated integration; it is not imported by the API at startup.

Included research modules:
- `volume_profile.py`: volume-at-price distributions, profile segments and profile modes.
- `tpo_profile.py`: time-price opportunity profiles.
- `multi_vwap.py`: daily, weekly, monthly and anchored VWAP calculations with bands.
- `order_flow_ticks.py`: tick-level buy/sell and delta/footprint-style aggregation.
- `order_flow_aggregated.py`: aggregated order-flow and profile analysis.
- `weis_wyckoff_system.py`: descriptive volume/price-structure analysis.
- `custom_mas.py` and `models_utils/`: supporting calculations and data structures.

## Liquidity analytics inventory

The existing core volume-indicator endpoint already covers OBV, ADL, Chaikin Oscillator, CMF, MFI, Force Index, Ease of Movement, VPT, NVI, PVI, VWAP, relative volume, volume oscillator, volume ROC and volume SMA.

The vendored library adds profile and tick-based research methods. The broader liquidity data model should distinguish the following input classes:

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

- https://github.com/srlcarlg/srl-python-indicators — Apache-2.0; vendored source described above.
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
