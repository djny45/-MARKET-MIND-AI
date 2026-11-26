# Master Execution Checklist — evidence-based

Baseline: branch `feat/four-market-terminal` @ `87137eed`, clean tree,
CI run `45844739454` success (7/7 jobs). PR #113 already merged at `cf396177`.
No duplicate modules will be created.

| # | Gap (from duplication audit) | Existing module to EXTEND | Action |
| --- | --- | --- | --- |
| 1 | 7 canonical USDT derivative/gold instruments missing | `instruments.py` | Add rows with contract-type/instrument-class detail |
| 2 | OKX taker volume, long/short ratio, mark price, funding history, liquidations, candles consumer | `exchange_intelligence.py` | Add endpoint keys + typed functions via existing `_fetch`/`LIMITER` |
| 3 | Deribit options chain/DVOL/perp, Hyperliquid funding/OI, XAU reference | `exchange_intelligence.py` | Add typed public-endpoint functions |
| 4 | Order-book replay library unused by API/UI | `main.py`, `IntelligencePanel.tsx` | Add replay route + panel using existing `reconstruct_order_book` |
| 5 | Taker-volume / long-short-ratio / basis analytics missing | `trade_flow.py` | Add deterministic functions over stored events |
| 6 | Stale/missing-field diagnostics for market events | `market_event_quality.py` | Extend diagnostics; no new module |
| 7 | Same-origin OKX relay with SSRF protection | new route modelled on `browser_research.py` | Fixed allowlist, bounded cache, no credentials |
| 8 | LLM no retry/active health check | `intelligence_core.py` | Bounded retry + safe active health check |
| 9 | Frontend backtesting/options/liquidation views | `App.tsx`, `IntelligencePanel.tsx` | Add views calling EXISTING backend APIs |

Deferred / not implemented with justification:
- Broker OAuth/token relay — credentials and provider approvals unavailable; strict research-only boundary retained.
- Tredye `data.tredye.com` endpoint — unauthorized; recorded as observation only.
- 550 independent models — architecture shares one core; documented accurately.
