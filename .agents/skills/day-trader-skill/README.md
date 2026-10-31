# Day-trader skill definitions

Upstream source: https://github.com/Jakeschincariol/day-trader-skill

The upstream `SKILL.md` playbooks are vendored here for MARKET-MIND-AI agents. This import contains skill instruction files only; it does not include upstream Python implementations, test fixtures, or Claude plugin metadata. Do not assume referenced scripts are installed.

## Available playbooks

- `trader-alerts/` — price and session alerts
- `trader-analyst/` — SEC filings and earnings analysis
- `trader-budget/` — position/risk-budget methodology (paper research only)
- `trader-entry/` — historical entry-pattern analysis (research only)
- `trader-exit/` — historical exit-rule analysis (research only)
- `trader-news/` — news and catalyst research
- `trader-pelosi/` — public congressional disclosure research
- `trader-risk/` — risk-rule validation (paper research only)
- `trader-scanner/` — market scan and chart-pattern screening
- `trader-timemachine/` — historical replay and Monte Carlo simulation

## Agent loading

Root `AGENTS.md` requires each agent to load only the playbook relevant to its task. Do not inject all skill documents into every agent prompt. Use outputs as research evidence, not trading recommendations. All results must disclose source timestamps, missing data, and whether values are simulated or observed.

## Exclusions

The upstream `trader-broker` order-execution skill is not copied or enabled. Entry/exit execution playbooks are not active. MARKET-MIND-AI remains a research and paper-simulation system; no brokerage order routing is permitted.

## License

See `LICENSE` for the upstream MIT license and copyright notice.
