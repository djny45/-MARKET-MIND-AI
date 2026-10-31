# Roadmap

This roadmap is a plan, not a claim that these features already exist. Mark an item complete only after implementation, tests, and documentation are merged.

## Phase 0 — Repository foundation
- [x] Define Bloomberg Terminal-inspired product scope.
- [x] Remove paper trading from product scope.
- [x] Exclude brokerage execution and order routing.
- [x] Add contribution guide and development standards.
- [x] Add CI for frontend TypeScript checks/build, backend compilation/tests, Python/npm dependency audits, and production container configuration/image builds plus a private Compose startup/proxy smoke test (general-purpose lint rules remain a follow-up).

## Phase 1 — Data and API foundation
- [x] Define canonical OHLCV bar and market-data batch schemas (instrument/event/document schemas remain open).
- [x] Implement provider-adapter protocol and retain the provider capability registry; live adapters remain pending.
- [x] Add retrieval timestamps, synthetic status labels, source provenance, and OHLCV validation for the fixture contract.
- [x] Add SQLite historical bar storage with source/status/retrieval provenance (retention policy remains open).
- [x] Add API health, readiness, and provider-status endpoints (liveness, SQLite readiness, explicit synthetic-only provider status).

## Phase 2 — Terminal user experience
- [ ] Build multi-panel workspace shell.
- [x] Add local persistent instrument watchlist with search-to-save, list, research handoff, and removal (single-user; authentication remains required before public deployment).
- [x] Add stored-data research modes for single and multi-timeframe comparison (chart workspace overlays remain open).
- [ ] Add market overview, heatmaps, and screeners.
- [ ] Add saved layouts and keyboard navigation.

## Phase 3 — Research and analytics
- [x] Implement tested indicator library and initial technical dictionary (SMA, EMA, RSI, MACD, Bollinger, volatility, ATR and candle-shape labels).
- [x] Add initial descriptive price-structure analytics: candle shapes, confirmed swing highs/lows, recent range references and ATR.
- [x] Integrate deep descriptive reports with OHLCV structural quality diagnostics.
- [x] Add relative-volume, return-volatility and historical drawdown diagnostics with explicit limitations.\n- [x] Add timestamp-aligned cross-asset historical return correlation with sample counts and insufficient-data handling.\n- [x] Add historical price-level clusters from repeated confirmed swing points, with configurable tolerance and confirmation windows.
- [x] Add timestamp-aligned market breadth counts, percentages and coverage with missing-data handling.\n- [x] Add consolidated deep-research dashboard summary with explicit unavailable sections.\n- [x] Add returns, volatility, correlation, drawdown, and descriptive weekday/calendar-month seasonality analytics (seasonality is non-predictive and sample-size dependent).
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
- [x] Add historical evidence export, SHA-256 verification, batch verification, and before/after comparison with provenance and diagnostic differences.
- [x] Add SQLite ingestion audit events and source/status data-lineage views (batch metadata only; no provider or user authentication claim).
- [ ] Add observability, performance profiling, and load tests.
- [ ] Add security review and dependency/licence inventory.
- [ ] Add backup, migration, and rollback procedures.
- [x] Publish reproducible private Docker deployment documentation (public deployment remains blocked on authentication and security controls).

## Acceptance criteria
A module is considered implemented only when it has:
1. A documented interface and configuration.
2. Automated tests, including failure and missing-data cases.
3. Data provenance and timestamp handling.
4. Security and licence review.
5. User-facing documentation and known limitations.
