---
name: autohedge-market-making-research
description: Advanced historical replay and statistical evaluation of AutoHedge's experimental market-making strategy using the imported trade logs; deterministic paper research only.
---

# Advanced AutoHedge market-making research

**Provenance:** Derived from `experimental/market_making.py` in
`The-Swarm-Corporation/AutoHedge` at commit
`c549c7950da112286e76725d49f6a25de8fa99bd`. The replay protocol below is an
extended, research-grade methodology.

**Required data:** imported logs in `data/autohedge/`:

| File | Bytes | Rows | SHA-256 (first 12) |
| --- | --- | --- | --- |
| `trades_20250305_193100.csv` | 30,294,201 | 300,807 | `548f93d66c69` |
| `trades_20250305_193129.csv` | 6,855,831 | 68,233 | `e9567764a60e` |

Full digests and schema are in `data/autohedge/README.md`. Verify before use.

**This is a synthetic fixture, not verified market evidence.** Timestamps carry
a non-standard `.f` suffix; prices for the same symbol and minute diverge
between the two files. Never present replay output as live or observed profit.

## 0. Boundary

No exchange connection, no order placement, no real inventory, no funds. Every
fill is simulated. Scope is historical replay, methodological study and paper
evaluation.

## 1. Data ingestion and quality gate

1. Verify both file digests. Record them in the run manifest.
2. Parse rows as: `<timestamp>, <symbol>, <BUY|SELL>, Price:<n>, Quantity:<n>, PnL:<n>`.
   Parse the numeric fields explicitly; normalize `.f` timestamps with a declared
   rule and keep the raw value for audit.
3. Build a quality report: symbols, row counts, timestamp range, side balance,
   non-finite values, duplicate rows, PnL field behaviour (zero on BUY in sampled
   records), and cross-file price divergence for matching symbol/minute.
4. Gate: if identity, schema or ordering cannot be established, stop and report
   `data_quality: insufficient`. Document the divergence finding as a limitation,
   not as a tradable signal.

## 2. Strategy specification (from upstream)

Config: `trading_pair`, `total_capital`, `spread_percentage`,
`order_size_percentage`, `max_inventory_exposure`, `rebalance_threshold`,
`min_profit_threshold`.

Order size = min(capital × order_size_percentage, capital × max_inventory_exposure)
/ reference price. Quotes are placed around the mid at the configured spread;
inventory is rebalanced when deviation exceeds the threshold. All fills are
simulated against the log's price stream.

## 3. Replay protocol

1. Order events chronologically; process one event at a time with no future
   information. Freeze config for the run and hash it.
2. Apply the inventory cap as a **hard constraint**: reject any simulated order
   that would breach it; record the rejection reason.
3. Model frictions explicitly: fee rate, half-spread cost, slippage as a function
   of order size, and an adverse-selection proxy (e.g. mark-to-mid immediately
   after a fill). Disclose if frictions are set to zero.
4. Track per event: quotes, simulated fills, base/quote inventory, cash, mark to
   market, and constraint violations. Persist the event ledger for audit.

## 4. Evaluation metrics

Report: initial/final equity, total and annualized return, PnL, max drawdown,
Sharpe/Sortino, hit rate, turnover, average inventory exposure, fill/rejection
ratio, and PnL attribution (spread capture vs inventory marking vs costs).
Compare against at least one simple baseline (e.g. buy-and-hold or static quote)
over the identical window.

## 5. Statistical rigor

- Use **chronological** train/validation/test splits; never shuffle time series.
- Walk-forward the parameter choice; fit on train, evaluate once on test.
- Bootstrap confidence intervals with a **block bootstrap** to preserve serial
  dependence; report intervals, not just point estimates.
- When sweeping spread / order size / inventory cap, disclose the full search
  space and apply a multiple-comparison correction. Report parameter stability
  across windows rather than the single best result.
- Treat negative results as first-class findings.

## 6. Reproducibility

Emit a run manifest containing: input file digests, config and config hash,
code revision, random seeds, friction assumptions, row counts processed,
exclusion rules, and a command or procedure to reproduce the run. Retain the
event ledger. No result is reportable without a manifest.

## 7. Output contract

A structured research note with: dataset identity and digests, quality findings
(including the divergence caveat), declared parameters, deterministic metrics
with confidence intervals, baseline comparison, parameter-sensitivity summary,
limitations, reproduction manifest, and `research_only: true; broker_execution: false`.
