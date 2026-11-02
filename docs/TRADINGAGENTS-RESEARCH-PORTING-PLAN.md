# TradingAgents research port checklist

**Status:** planning/documentation only. This file does not claim that upstream code has been vendored or that provider integrations are implemented.

## Goal

Reuse compatible, license-compliant **data research** ideas from [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) while keeping MARKET-MIND-AI's existing architecture, validation, provenance, and research-only boundary.

## Source references

- Upstream repository: https://github.com/TauricResearch/TradingAgents
- Router: https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/dataflows/router.py
- Default configuration: https://github.com/TauricResearch/TradingAgents/blob/main/tradingagents/default_config.py
- Existing local integration guide: [TRADINGAGENTS-MARKET-DATA-INTEGRATION.md](TRADINGAGENTS-MARKET-DATA-INTEGRATION.md)
- Research skill: [tradingagents-market-data-research](../.agents/skills/tradingagents-market-data-research/SKILL.md)

## Phased completion checklist

### Phase 1 — Provenance and scope
- [x] Record upstream project, license, and source links.
- [x] Map upstream data-source categories.
- [x] Explicitly exclude prediction-market functionality.
- [ ] At source-import time, record the exact upstream commit SHA and license/NOTICE files.
- [ ] Review each imported file and its dependencies for license compatibility.

### Phase 2 — Provider interface design
- [ ] Define a provider-neutral interface for historical market data.
- [ ] Define normalized data contracts for OHLCV, timestamps, symbol identifiers, and source metadata.
- [ ] Include provider name, retrieval time, requested interval, and data freshness in every research result.
- [ ] Keep credentials out of source code, logs, examples, and test fixtures.
- [ ] Document API limits, terms, and graceful behavior when a provider is unavailable.

### Phase 3 — Data-quality safeguards
- [ ] Reject malformed rows and non-finite numeric values.
- [ ] Validate timestamp ordering, duplicates, missing intervals, and timezone normalization.
- [ ] Validate OHLC consistency (high/low bounds and nonnegative volume where applicable).
- [ ] Add deterministic fixtures using synthetic data; tests must not call paid APIs.
- [ ] Add tests for provider errors, empty results, malformed payloads, and stale data.

### Phase 4 — Research-only analysis
- [ ] Expose descriptive historical statistics and data-quality summaries only.
- [ ] Clearly label results as historical, educational, and non-predictive.
- [ ] Avoid personalized financial recommendations, executable entry/exit instructions, or trade alerts.
- [ ] Keep any future simulation isolated from brokerage credentials and order APIs.

### Phase 5 — Verification
- [ ] Run formatting, static checks, and unit tests.
- [ ] Inspect dependency/license notices.
- [ ] Verify CI on the exact commit.
- [ ] Update README with only features confirmed by code and tests.

## Explicitly out of scope

- Brokerage connectivity or order placement, modification, and cancellation.
- Live trading automation or trade execution.
- Trading signals, personalized buy/sell/hold recommendations, or position sizing.
- Prediction-market modules.
- Claims that upstream components are “copied,” “installed,” or “working” before a verified source import and tests exist.

## Completion criteria

A phase is complete only when its checklist items are implemented in code or documentation as appropriate, reviewed, and backed by test/CI evidence. This checklist is a plan—not proof that those phases have been completed.
