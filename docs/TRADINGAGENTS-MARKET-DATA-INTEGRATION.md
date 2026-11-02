# TradingAgents market-data research integration

## Upstream reference

- Project: [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)
- Upstream license: Apache License 2.0 ([LICENSE](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE))
- Upstream README: [Market/data framework overview](https://github.com/TauricResearch/TradingAgents/blob/main/README.md)

TradingAgents is a broader multi-agent financial trading research framework. This repository adopts **selected market-data design ideas only**: provider routing, typed data-unavailable outcomes, source-aware adapters, point-in-time controls, and graceful degradation. It does not vendor the upstream full application or its trading decision/execution modules.

## What was added

- `.agents/skills/tradingagents-market-data-research/SKILL.md`: reusable agent playbook for data provider integration, provenance, point-in-time integrity, quality checks and source-linked reporting.
- This document: integration scope, attribution, and project-specific constraints.

## How it fits MARKET-MIND-AI

MARKET-MIND-AI already has a normalized OHLCV contract, provider adapter protocol, SQLite market-bar storage, audit events, data lineage endpoints, and historical evidence exports. The skill instructs contributors to reuse these interfaces rather than create duplicate routers or storage.

| Upstream concept | MARKET-MIND-AI adaptation |
|---|---|
| Provider/vendor routing | Explicit configured adapter routing; no silent vendor switch |
| Vendor-specific dataflows | Existing adapter protocol and canonical schemas |
| No-data/unavailable outcomes | Typed status/error distinctions; no zero-filled fabricated records |
| Point-in-time safeguards | Event/publication/retrieval timestamps; as-of filtering and tests |
| Data-source reporting | Existing lineage, audit, export and verification features |
| Optional vendor resilience | Independent source failures with transparent missing-data labels |

## Data source examples

The skill mentions Yahoo Finance, Alpha Vantage, SEC EDGAR, FRED, EIA, CoinGecko, official exchange APIs, ECB reference data, and RSS/Atom only as **potential source categories/examples**. It does not configure or activate any of them.

Before implementation, check current official documentation, coverage, rate limits, API-key requirements, exchange entitlements, commercial terms, and redistribution restrictions. A public API or open-source library does not automatically grant market-data redistribution rights.

## Deliberately excluded

This integration does not add the upstream trader, portfolio manager, risk-debate-to-order flow, broker adapter, order placement, automated trading, or prediction-market integrations. MARKET-MIND-AI remains a source-grounded research application with no brokerage execution.

## Attribution and license

The integration is an original adaptation of public architectural concepts from TradingAgents. No upstream source-code files are copied by this change.

TradingAgents is identified by its authors as an Apache-2.0 project. If future contributors copy or modify upstream source files, they must retain the applicable copyright/license notices, include the Apache-2.0 license, mark modified files, and preserve any applicable NOTICE attributions. Review the upstream license and notices at the time of copying.

## Verification

The skill is guidance, not an active provider integration. It does not install dependencies, configure API keys, start provider connections, or establish that any data source is live. Live provider status must come from the existing provider-health mechanism and authorized credentials.
