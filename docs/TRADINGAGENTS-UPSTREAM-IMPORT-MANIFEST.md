# TradingAgents upstream integration manifest

**Status:** research-only integration plan  
**Target:** MARKET-MIND-AI  
**Upstream:** [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents)  
**License:** Apache-2.0 (review upstream LICENSE and NOTICE before copying any source)

## Purpose

This manifest records what can be reused from TradingAgents to improve MARKET-MIND-AI's market-data research and data-quality layer. It is not a claim that the upstream repository has been cloned or vendored. No upstream source files are included by this document-only change.

## Allowed research/data concepts

- Source-aware market-data provider routing and configuration patterns.
- Provider-specific data retrieval for historical OHLCV and public company filings, where access terms permit.
- Data provenance: source, retrieval time, publication/filing time, and as-of date.
- Explicit unavailable/partial/stale data states rather than fabricated values.
- Point-in-time validation and tests against look-ahead leakage.
- Provider health, timeout, retry, rate-limit, and cache behavior, with transparent reporting.
- Documentation, schemas, fixtures, and tests for read-only research data.

## Excluded from this integration

Do not copy or wire up upstream modules that generate buy/sell/hold recommendations, debate trading decisions, calculate trade sizing, manage portfolios for trading, backtest strategies for profit, connect brokers, place/cancel orders, or run autonomous trading. Exclude prediction-market integrations as well.

## Integration approach

1. Inspect upstream files at a pinned commit/tag before any source reuse; do not track a moving `main` branch for reproducibility.
2. Identify the smallest data-only module and its transitive dependencies. Do not copy the entire framework.
3. Check compatibility with MARKET-MIND-AI's existing adapter protocol and canonical OHLCV schema before adding code.
4. Keep upstream provenance in each copied/modified file and retain the Apache-2.0 license, copyright notices, and any applicable NOTICE file. Mark modifications.
5. Review API terms, data redistribution rights, rate limits, credentials, and point-in-time semantics for each provider.
6. Add deterministic tests for missing values, invalid timestamps, duplicate bars, stale data, provider errors, and source attribution.
7. Keep credentials out of source control and never enable provider access by default.
8. Run the repository's existing lint/test/CI workflow and report the actual result; do not claim a pass before it completes.

## Upstream source map (reference only)

- [README](https://github.com/TauricResearch/TradingAgents/blob/main/README.md)
- [Dataflow router](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/router.py)
- [Default configuration](https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/default_config.py)
- [License](https://github.com/TauricResearch/TradingAgents/blob/main/LICENSE)

The upstream repository is actively maintained. Pin the exact revision used during implementation and re-check its license and file layout before importing anything; paths and APIs can change between releases.

## Completion criteria

- [ ] A pinned upstream revision is recorded.
- [ ] Every reused file is listed with source path, original license, and modifications.
- [ ] Only read-only research/data components are imported.
- [ ] Existing MARKET-MIND-AI interfaces are reused; no parallel duplicate data router/storage is introduced.
- [ ] Tests and CI are run and their status recorded.
- [ ] README accurately distinguishes documentation, imported code, and working integrations.
