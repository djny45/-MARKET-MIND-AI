# TradingAgents upstream reference

This directory records provenance and integration boundaries for the upstream project. It does **not** contain a vendored copy of TradingAgents.

## Upstream

- Project: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- License: Apache-2.0 (see the upstream repository's LICENSE file)
- Upstream README: https://github.com/TauricResearch/TradingAgents/blob/main/README.md
- Data-source router: https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/router.py
- Default configuration: https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/default_config.py

## Integration status

MARKET-MIND-AI currently keeps a research-oriented adaptation guide rather than importing the upstream application wholesale. See:

- [Market-data integration guide](../../docs/TRADINGAGENTS-MARKET-DATA-INTEGRATION.md)
- [Research skill](../../.agents/skills/tradingagents-market-data-research/SKILL.md)

The documented data-source categories include OHLCV, technical indicators, fundamentals, financial statements, news/insider metadata, and macroeconomic series. Provider availability, API terms, rate limits, and data freshness must be checked before implementation.

## Scope and safety boundary

- This folder is an attribution/provenance record, not a functioning upstream clone.
- Do not add brokerage credentials or enable brokerage order placement, modification, or cancellation.
- Keep any imported work limited to data ingestion, validation, historical research, documentation, and non-actionable educational analysis.
- Do not import transaction execution, live trading, or prediction-market modules into this repository.
- Do not claim upstream features are installed or operational unless code, tests, and CI verify them.

## License and attribution

TradingAgents is a separate upstream project under Apache-2.0. Before copying any upstream source files into this repository, preserve its license and copyright notices, include required NOTICE material if present, record the exact upstream commit, and review dependency licenses. This file alone does not grant rights beyond the upstream license.

## Why this is not a full source copy

A full upstream checkout is maintained by its authors and changes independently. A provenance record and selective integration are easier to audit than silently mixing two codebases. Use the upstream repository for the complete source and release history.
