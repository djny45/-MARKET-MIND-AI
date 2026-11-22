# Shadow tracking and demotion-cycle automation (research-only)

`backend/app/shadow_tracker.py` builds on the deterministic shadow-order
engine and provides daily performance aggregation, strategy evaluation, and
ten-cycle demotion rules. Research-only; no execution.

## Rules

- A cycle is **failing** if the day's total PnL is negative or itsSharpe is
  below the recent baseline.
- A strategy is **demoted** after 10 consecutive failing cycles.
- A demoted strategy recovers after 10 clean cycles.
- All demotion/recovery decisions are human-approved; the engine only proposes.

## API

```python
from app.research_shadow_session import ShadowSessionEngine, make_backtest_config
from app.shadow_tracker import ShadowTracker

tracker = ShadowTracker(ShadowSessionEngine(make_backtest_config()))
tracker.record_shadow_order("BTC", {
    "side": "BUY", "quantity": 1.0, "reference_price": 100.0,
    "expected_pnl": 1.2, "timestamp": "2026-11-22T09:00:00",
}, run_id="r1")
tracker.evaluate_strategies()        # per-symbol failing/recovery counts
tracker.generate_demotion_proposals()# pending human-required demotion proposals
tracker.demote("BTC", "ops-1", "underperformed")
tracker.recover("BTC", "ops-1", "recovered")
tracker.report()                     # dashboard-style summary
```

## Audit

Every change is appended to the audit log (`data/shadow_tracker_audit.jsonl`);
read it with `read_tracker_audit`.

Covered by 5 tests in `backend/tests/test_shadow_tracker.py`.
