# Roadmap

This roadmap is a plan, not a claim that features already exist. Mark an item complete only after implementation, tests, and documentation are merged.

## Phase 0 — Repository foundation
- [x] Define research-terminal product scope.
- [x] Exclude brokerage execution and order routing.
- [x] Add contribution guide and development standards.
- [x] Add CI for frontend build, backend compilation/tests, dependency audits, production Compose validation, container startup/proxy smoke tests, and backup/restore round-trip checks.

## Phase 1 — Data and API foundation
- [x] Define canonical OHLCV bar and market-data batch schemas.
- [x] Implement provider-adapter protocol and capability registry; live adapters remain pending.
- [x] Add retrieval timestamps, synthetic status labels, source provenance, and OHLCV validation.
- [x] Add SQLite historical bar storage with source/status/retrieval provenance.
- [x] Add API health, readiness, and provider-status endpoints.

## Phase 2 — Terminal user experience
- [ ] Build multi-panel workspace shell.
- [x] Add local persistent instrument watchlist with search-to-save, list, research handoff, and removal (single-user; authentication remains required before public deployment).
- [x] Add stored-data research modes for single and multi-timeframe comparison.
- [ ] Add market overview, heatmaps, and screeners.
- [ ] Add saved layouts and keyboard navigation.

## Phase 3 — Research and analytics
- [x] Implement tested indicator library and initial technical dictionary.
- [x] Add descriptive price-structure analytics, including candle shapes, confirmed swing points, range references, and ATR.
- [x] Integrate deep descriptive reports with OHLCV structural quality diagnostics.
- [x] Add relative-volume, return-volatility, historical drawdown, and timestamp-aligned cross-asset correlation diagnostics.
- [x] Add historical price-level clusters from repeated confirmed swing points.
- [x] Add timestamp-aligned market breadth counts, percentages, and coverage with missing-data handling.
- [x] Add consolidated deep-research dashboard summary with explicit unavailable sections.
- [x] Add descriptive weekday/calendar-month seasonality analytics with sample-size limitations.
- [ ] Add fundamentals, filings, news, and macro research panels.
- [ ] Add source-cited research reports and exportable methodology notes.
- [ ] Add historical evaluation framework with bias and data-quality checks.

## Phase 4 — Intelligence and workflow canvas
- [ ] Define complete typed specialist-worker input/output contracts.
- [x] Add versioned v1.0.0 contract definitions and runtime shape validation for all 10 currently supported workflow node types; detailed domain schemas and mandatory provenance enforcement remain pending.
- [ ] Build central research orchestrator with model-backed inference and evidence-grounded synthesis.
- [x] Add initial shared-core worker registry and deterministic routing for supported workflow node types.
- [ ] Add worker registry versioning and a broader evaluation suite.
- [x] Add append-only worker-scoped evidence memory with provenance and quality labels.
- [ ] Add reviewed shared knowledge, memory lifecycle controls, and human approval workflows.

Current boundary: worker routing invokes existing deterministic Python handlers. The 550 profiles are not independent models; LLM inference, autonomous self-learning, and brokerage execution remain disabled.
- [ ] Build visual node-based research workflows.
- [ ] Add explainability, evidence coverage, and disagreement reporting.

## Phase 5 — Reliability and governance
- [x] Add historical evidence export, SHA-256 verification, batch verification, and before/after comparison with provenance.
- [x] Add SQLite ingestion audit events and source/status data-lineage views.
- [x] Add SQLite backup with integrity verification and SHA-256 digest.
- [x] Add safe SQLite restore with source/target verification, atomic replacement, and overwrite protection.
- [x] Add CI backup/restore round-trip test inside the production API image.
- [x] Add private Docker deployment documentation, resource limits, dropped Linux capabilities, no-new-privileges, and rotating container logs.
- [ ] Add observability, performance profiling, and load tests.
- [ ] Add security review and dependency/licence inventory.
- [ ] Complete host-specific backup/restore drills, retention policy, migration rollback, and incident procedures.
- [ ] Add authentication/authorization and TLS ingress before any public deployment.

## Acceptance criteria

A module is considered implemented only when it has:
1. A documented interface and configuration.
2. Automated tests, including failure and missing-data cases.
3. Data provenance and timestamp handling where relevant.
4. Security and licence review.
5. User-facing documentation and known limitations.
