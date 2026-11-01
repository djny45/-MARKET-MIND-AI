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
- [x] Version the deterministic worker contract and expose contract version in capabilities and dispatch responses.
- [x] Add bounded deterministic worker dispatch with explicit capability authorization and a capability-status API.
- [x] Add a typed evidence-first research aggregation API with market coverage, source references, quality labels and disagreement reporting.
- [x] Add provenance-gated cross-market research round assembly and read-only API.\n- [ ] Build central research orchestrator.
- [x] Add deterministic worker capability smoke-evaluation suite and read-only evaluation API.\n- [x] Add fixed analytical reference-vector correctness benchmarks and a read-only evaluation API.\n- [ ] Add broader property-based, independent-library, and longitudinal benchmark coverage.\n- [ ] Add worker registry governance.
- [x] Add isolated append-only worker research memory with source references and pending-review status.\n- [ ] Add human-reviewed promotion into shared knowledge.
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

## Worker evaluation contract

The `GET /api/workers/evaluations` endpoint runs one fixed synthetic fixture per unique deterministic operation currently mapped to worker profiles. It checks successful dispatch and basic output shape. A passing result confirms wiring only; it does not validate analytical correctness, predictive skill, live-data quality, or trading performance. The endpoint is read-only and does not access external providers or execute orders.

## Cross-market research rounds

The `GET /api/agent-network/round` endpoint assembles already-published India, US, crypto and forex research messages. It reports per-market message counts, distinct source-reference coverage, quality-label counts, and a human-review gate. A round is marked incomplete when any requested market lacks the configured minimum number of distinct source references. Passing this gate checks provenance coverage only: it does not authenticate sources or validate findings. The workflow is deterministic and does not invoke independent LLM agents.


## Analytical correctness benchmarks

The `GET /api/analytics/benchmarks` endpoint checks fixed hand-computable vectors for SMA, EMA, returns, RSI, MACD, Bollinger bands, and realized volatility. It checks formula behavior and output values for a narrow deterministic fixture set. Passing does not establish correctness across all edge cases, data vendors, market regimes, or predictive performance. The SMA test explicitly records the implementation's current partial-window convention. No live data or order execution is involved.
