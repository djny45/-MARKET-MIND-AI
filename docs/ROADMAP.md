# Roadmap

This roadmap is a plan, not a claim that these features already exist. Mark an item complete only after implementation, tests, and documentation are merged.

## Phase 0 — Repository foundation
- [x] Define Bloomberg Terminal-inspired product scope.
- [x] Remove paper trading from product scope.
- [x] Exclude brokerage execution and order routing.
- [ ] Add contribution guide and development standards.
- [ ] Add CI for linting, type checks, tests, and dependency scanning.

## Phase 1 — Data and API foundation
- [x] Define canonical OHLCV bar and market-data batch schemas (instrument/event/document schemas remain open).
- [x] Implement provider-adapter protocol and retain the provider capability registry; live adapters remain pending.
- [x] Add retrieval timestamps, synthetic status labels, source provenance, and OHLCV validation for the fixture contract.
- [x] Add SQLite historical bar storage with source/status/retrieval provenance (retention policy remains open).
- [ ] Add API health, readiness, and provider-status endpoints.

## Phase 2 — Terminal user experience
- [ ] Build multi-panel workspace shell.
- [ ] Add global instrument search and watchlists.
- [x] Add stored-data research modes for single and multi-timeframe comparison (chart workspace overlays remain open).
- [ ] Add market overview, heatmaps, and screeners.
- [ ] Add saved layouts and keyboard navigation.

## Phase 3 — Research and analytics
- [x] Implement tested indicator library and initial technical dictionary (SMA, EMA, RSI, MACD, Bollinger, volatility, ATR and candle-shape labels).
- [x] Add initial descriptive price-structure analytics: candle shapes, confirmed swing highs/lows, recent range references and ATR.
- [x] Integrate deep descriptive reports with OHLCV structural quality diagnostics.
- [x] Add relative-volume, return-volatility and historical drawdown diagnostics with explicit limitations.
- [ ] Add returns, volatility, correlation, drawdown, breadth, and seasonality analytics.
- [ ] Add fundamentals, filings, news, and macro research panels.
- [ ] Add source-cited research reports and exportable methodology notes.
- [ ] Add historical evaluation framework with bias and data-quality checks.

## Phase 4 — Intelligence and workflow canvas
- [ ] Define typed specialist-worker contracts.
- [ ] Build central research orchestrator.
- [ ] Add worker registry, versioning, and evaluation suite.
- [ ] Add worker-specific research memory and reviewed shared knowledge.
- [ ] Build visual node-based research workflows.
- [ ] Add explainability, evidence coverage, and disagreement reporting.

## Phase 5 — Reliability and governance
- [ ] Add audit logs and data lineage views.
- [ ] Add observability, performance profiling, and load tests.
- [ ] Add security review and dependency/licence inventory.
- [ ] Add backup, migration, and rollback procedures.
- [ ] Publish reproducible deployment documentation.

## Acceptance criteria
A module is considered implemented only when it has:
1. A documented interface and configuration.
2. Automated tests, including failure and missing-data cases.
3. Data provenance and timestamp handling.
4. Security and licence review.
5. User-facing documentation and known limitations.
