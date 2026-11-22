# AutoHedge-derived Risk Assessment Research Skill

**Upstream:** [The-Swarm-Corporation/AutoHedge](https://github.com/The-Swarm-Corporation/AutoHedge)  
**Adaptation:** MARKET-MIND-AI research-only profile.  
**Licence:** MIT; see `NOTICE.md` in this directory.

## Purpose
Explain market, data, model, liquidity, volatility, correlation, and operational risks in a research report. This skill does not size or manage real positions.

## Procedure
1. Identify the instrument, observation horizon, data source, and assumptions.
2. Check volatility, drawdown history, liquidity indicators, gaps, concentration, correlation, and regime changes when data supports them.
3. Distinguish historical observations from hypothetical stress scenarios.
4. Describe tail risk and model risk; state where VaR or expected-shortfall estimates are unreliable due to sample size or distribution assumptions.
5. Evaluate source, timestamp, missing-data, and survivorship risks.
6. Present several plausible adverse scenarios without assigning false precision.
7. List mitigations at the system/research-process level: data validation, independent review, limits on claims, monitoring, and rollback of software changes.

## Required output
- Risk categories and evidence
- Historical metrics with sample and method
- Scenario analysis and assumptions
- Model/data limitations
- Controls and unresolved risks

## Guardrails
- Do not calculate personalized capital allocation, leverage, or trade position sizes.
- Do not issue instructions to enter, exit, or hold financial positions.
- Do not imply that risk controls eliminate loss.
- No brokerage, wallet, order, or signing access.
