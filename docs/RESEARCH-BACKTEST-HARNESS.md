# Research backtest harness (paper only)

`backend/app/research_backtest_harness.py` is a deterministic, auditable
backtesting engine for research. It has **no broker connection**, no credentials,
and no live capability. Every order it produces is a `shadow_order` record with
`executed: false` and `mode: "shadow_log_only"`.

## Guarantees

- Chronological train/validation/test splits — never shuffled.
- Explicit fee and slippage assumptions in basis points; costs reduce equity.
- Signals may only use bars strictly before the decision bar (no lookahead).
- Long/flat only — no shorting, leverage, or margin.
- Multiple-testing correction: Benjamini–Hochberg q-values across all candidates.
- Promotion requires corrected significance **and** positive out-of-sample Sharpe.
- Reproducibility manifest: data digest, config digest, seed, bar count, cost model.
- Hypothesis registry: append-only records with status transitions.

## Usage

```python
from app.research_backtest_harness import (
    BacktestConfig, Hypothesis, HypothesisRegistry,
    evaluate_candidates, generate_synthetic_bars,
    momentum_signal, mean_reversion_signal, run_backtest,
)

bars = generate_synthetic_bars(500, seed=7)   # replace with validated historical bars
config = BacktestConfig(seed=7, fee_bps=5, slippage_bps=2)

registry = HypothesisRegistry()
registry.register(Hypothesis("h-001", "momentum beats mean reversion", {"lookback": 10}))

result = evaluate_candidates(bars, {
    "momentum": momentum_signal(10),
    "mean_reversion": mean_reversion_signal(10),
}, config)

single = run_backtest(bars, momentum_signal(10), config)
print(single["manifest"], single["shadow_orders"][:2])
```

`generate_synthetic_bars` is for harness validation only. Real research must use
validated historical data with documented provenance; synthetic fixtures must
never be reported as market evidence.

## Boundaries

This is the research-side loop only. It does not connect to brokers, place
orders, hold keys, train or deploy models autonomously, or grant permissions.
Strategy promotion is a reviewed decision supported by the harness output, not
an automatic action. It is covered by 9 tests in
`backend/tests/test_research_backtest_harness.py`.
