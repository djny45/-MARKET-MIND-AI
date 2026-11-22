---
name: autohedge-market-making-research
description: Study AutoHedge's experimental market-making strategy and replay it against the imported historical trade logs; historical simulation and paper research only.
---

# AutoHedge experimental market-making research

**Provenance:** Derived from `experimental/market_making.py` in
`The-Swarm-Corporation/AutoHedge` at commit
`c549c7950da112286e76725d49f6a25de8fa99bd`.

**Required data:** the imported AutoHedge trade logs in `data/autohedge/`:

| File | Bytes | Rows |
| --- | --- | --- |
| `trades_20250305_193100.csv` | 30,294,201 | 300,807 |
| `trades_20250305_193129.csv` | 6,855,831 | 68,233 |

Precomputed SHA-256 digests are recorded in `data/autohedge/README.md`. Verify them
before analysis. The logs are a **synthetic/simulated fixture**, not verified market
evidence: timestamps carry a non-standard `.f` suffix, and prices for the same
symbol and minute differ across the two files. Never present them as live or
authoritative market data.

## Boundary

This skill studies and replays a strategy. It does **not** connect to an exchange,
place orders, manage real inventory, or move funds. All fills are simulated.

## Strategy parameters (from the source)

`MarketMakingConfig`: `trading_pair`, `total_capital`, `spread_percentage`,
`order_size_percentage`, `max_inventory_exposure`, `rebalance_threshold`,
`min_profit_threshold`. Order size is the lesser of a capital fraction and the
maximum inventory exposure divided by price; quotes are placed around the mid at
the configured spread, then inventory is rebalanced when deviation exceeds the
threshold.

## Research workflow

1. Load and validate the CSV schema: `timestamp`, symbol, side, `Price:<value>`,
   `Quantity:<value>`, `PnL:<value>`. Parse the numeric fields explicitly; do not
   assume a standard datetime parser accepts the `.f` suffix.
2. Profile coverage: symbols, row counts, timestamp range, side balance, missing
   values, duplicate rows, and PnL distribution. Report the price divergence between
   the two files as a data-quality finding.
3. Replay the strategy deterministically with the config above. Track bid/ask
   quotes, simulated fills, base/quote inventory, and total value. Apply the
   inventory cap as a hard constraint.
4. Evaluate with chronological separation: report initial capital, final value,
   total return %, trade count, drawdown, and sensitivity to spread / order size /
   inventory cap. Compare with a simple baseline.
5. Document assumptions, cost/slippage model, data caveats, and reproducibility
   metadata (input digests, parameters, code revision). Any "profit" is a
   simulation result, not live performance.

## Output contract

A structured research note with: dataset identity and digests, validation findings,
parameters, deterministic metrics, baseline comparison, limitations, and the
statement `research_only: true; broker_execution: false`.
