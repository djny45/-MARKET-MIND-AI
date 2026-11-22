# AutoHedge-derived Quantitative Analysis Research Skill

**Upstream:** [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge)  
**Adaptation:** MARKET-MIND-AI research-only profile.  
**Licence:** MIT; see `NOTICE.md` in this directory.

## Purpose
Evaluate supplied market and time-series datasets with transparent descriptive statistics, technical features, and reproducible validation.

## Procedure
1. Validate schema, instrument identifiers, timezone, frequency, units, missing values, duplicates, corporate actions, and timestamp freshness.
2. Describe sample coverage before calculating indicators. State when the sample is too short or incomplete.
3. Calculate only features supported by the supplied data. Label indicators as descriptive transformations, not predictive facts.
4. Evaluate trend, momentum, volatility, volume, correlation, seasonality, and regime hypotheses where applicable.
5. For historical model evaluation, use chronological splits; fit preprocessing on training data only; check look-ahead leakage, survivorship bias, and overlapping windows.
6. Compare against a simple baseline. Report sample sizes, uncertainty, stability across periods, and sensitivity to assumptions.
7. Make calculations reproducible: include formula definitions, input ranges, configuration, and data references.

## Required output
- Data-quality report and coverage
- Feature definitions and calculated values
- Statistical observations and competing interpretations
- Baseline comparison and robustness checks, when applicable
- Uncertainty, limitations, and reproducibility details

## Guardrails
- Never fabricate missing prices, volumes, or observations.
- Do not convert descriptive metrics into trade instructions, entry/exit levels, position sizes, or return promises.
- Do not call a backtest proof of future performance.
- Do not access wallets, brokerage accounts, order APIs, or transaction-signing tools.
