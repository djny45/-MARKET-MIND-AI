# 24-hour shadow rule for new strategies

`backend/app/shadow_rule.py` implements Phase 4 of the research-loop engine.
New strategies are shadow-tracked first; production eligibility is invisible
until the 24-hour observation window and minimum evaluation requirements are
met. Human approval is always required.

## Rules

- **24-hour window**: promotion eligibility requires ≥24 hours of shadow
  tracking.
- **Minimum evaluation**: at least 3 evaluation cycles with positive total PnL
  and no failing cycles.
- **Failure detection**: any negative-PnL cycle blocks eligibility.
- **Isolation**: each strategy is tracked in its own isolated shadow session.
- **Human approval**: `requires_human_approval` is always `True`.

## API

```python
from app.shadow_rule import ShadowRuleEngine

engine = ShadowRuleEngine()
engine.register_strategy("BTC")                         # start 24h clock
eligibility = engine.promotion_eligibility("BTC")        # detailed eligibility report
eligible = engine.passed_minimum_evaluation("BTC")       # bool
reports = engine.report()["strategies"]                  # dashboard-style summaries
```

## Boundaries

- Eligibility reports are read-only research data; promotion still requires
  human approval and changes the shadow-tracker status.
- Resets: if a strategy is demoted by the shadow-tracker, the rule can gate
  new cycles before re-eligibility.

Covered by 6 tests in `backend/tests/test_shadow_rule.py`.
