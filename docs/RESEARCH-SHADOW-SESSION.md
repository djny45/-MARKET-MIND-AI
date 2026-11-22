# Shadow session engine and daily simulated reports

`backend/app/research_shadow_session.py` is the paper-only shadow-order engine
for the research platform. It builds on the deterministic backtest harness.

## Guarantees

- Every recorded order is `executed: false` and `mode: "shadow_log_only"`.
- Full audit trail: the `data/research_shadow_log.jsonl` file receives every
  shadow order record as it is logged.
- Metrics: gross PnL, net PnL, daily PnL, trade count, Sharpe and Sortino using
  252 business days/year assumptions, and max drawdown from a normalized equity
  curve.
- Inputs required per order: symbol, side (`BUY`/`SELL`), quantity, reference
  price, timestamp; optional notional, cost, expected PnL and rationale.

## Usage

```python
from app.research_shadow_session import (
    ShadowSessionEngine, make_backtest_config, replay_audit_log, shadow_metrics_from_log,
)

engine = ShadowSessionEngine(make_backtest_config())
engine.begin_run("daily-2026-11-22")

engine.record_shadow_order({
    "symbol": "BTCUSDT", "side": "BUY", "quantity": 1.5,
    "reference_price": 100.0, "expected_pnl": 0.8,
    "rationale": "hypothesis: momentum edge", "timestamp": "2026-11-22T09:00",
}, run_id="daily-2026-11-22")

orders = engine.list_orders("daily-2026-11-22")
metrics = engine.metrics("daily-2026-11-22")

# Read the append-only audit log and aggregate from it instead:
records = replay_audit_log(engine.log_path)
aggregate = shadow_metrics_from_log(engine.log_path)
```

## Boundaries

- Log-only by construction: there is no execution path and no credential use.
- Records are hypotheses, not Fill events. Expectations (`expected_pnl`) model
  hypothetical PnL; only paper accounting flows into the metrics.
- Reports are research-only; do not treat drawdowns from shadows as realized
  losses or claims as market performance.

Covered by 5 tests in `backend/tests/test_research_shadow_session.py`.
