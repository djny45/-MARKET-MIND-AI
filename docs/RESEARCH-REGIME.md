# Regime and drift detection (research-only)

`backend/app/research_regime.py` provides deterministic regime classification
and drift signals for research workflows. It is the first phase of the
research-loop engine.

## Regimes

- `TREND_UP` — recent mean return above 0.05% per bar and low volatility
- `TREND_DOWN` — recent mean return below -0.05% per bar and low volatility
- `HIGH_VOL` — recent daily volatility at or above 4 bp
- `LOW_VOL` — recent volatility below 1 bp
- `MIXED` — otherwise

## Drift report

`drift_report(returns, split=0.5, window=20)` splits the series chronologically,
computes baseline and current regimes, and returns a normalized drift score with
a signal flag. A drift is signalled when the regime label changes or the score
exceeds 1.5.

## Usage

```python
from app.research_regime import detect_regime, drift_report

regime = detect_regime(returns)          # current regime on the last 20 bars
report = drift_report(returns)           # baseline vs current with drift score
```

Research-only: reads historical/synthetic returns and returns reports; it never
executes orders or claims market performance. Covered by 10 tests in
`backend/tests/test_research_regime.py`.
