# AutoHedge-derived Market-Making Research Lab

**Upstream:** [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge)  
**Adaptation:** MARKET-MIND-AI research-only implementation.  
**Licence:** MIT; see the sibling `NOTICE.md`.

## Purpose
Evaluate supplied order-book snapshots, spread hypotheses, inventory sensitivity, and transaction-cost assumptions using pure calculations and in-memory simulated fills.

## Workflow
1. Verify the supplied order book has positive finite bid/ask values, a valid uncrossed spread, a plausible timestamp, and supported units.
2. Reject stale or future-dated snapshots rather than silently substituting prices.
3. Calculate indicative quote levels from an explicit spread and optional inventory-skew assumption.
4. Report quote levels as analysis only; never serialize them into broker/order API payloads.
5. Use the pure `simulate_fill` helper to understand inventory and fee arithmetic using explicitly supplied synthetic balances.
6. Test sensitivity across spreads, fees, liquidity assumptions, and observation windows.
7. Document that a simple quote/fill calculation does not model queue position, adverse selection, partial fills, venue fees, latency, market impact, or exchange rules.

## Required output
Data timestamp and source; book validation; mid/spread; indicative quote calculations; assumed balances and fees for simulated arithmetic; limitations.

## Guardrails
No exchange connection, order placement, order cancellation, wallet access, private keys, transaction signing, or capital allocation. No background polling loop. Never present simulated fills as executed trades or realised performance.
