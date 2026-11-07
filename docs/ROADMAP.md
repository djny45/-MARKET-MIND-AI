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
- [ ] Add historical evaluation framework with bias and data-quality checks.\n  - [x] Add a research-only binary classification metric summary (confusion matrix, accuracy, precision, recall, specificity, balanced accuracy, F1, class prevalence) and majority-class baseline comparison;
- [x] Add split-level binary research evaluation aggregation with per-split metrics, pooled metrics, and fold variability; this is metric aggregation only, not evidence of model performance; metrics operate only on caller-supplied labels/predictions.\n  - [x] Add a research-only dataset metadata gate (source/symbol/timeframe, timezone-aware date range, sample count, missing fraction, synthetic-data flag); this does not inspect underlying bars or establish evaluation validity.

## Phase 4 — Intelligence and workflow canvas
- [ ] Define complete typed specialist-worker input/output contracts.
- [x] Add versioned v1.0.0 contract definitions and runtime shape validation for all 10 currently supported workflow node types; detailed domain schemas and mandatory provenance enforcement remain pending.
- [ ] Build central research orchestrator with model-backed inference and evidence-grounded synthesis.\n- [x] Add an optional single-core local Ollama provider boundary (loopback-only, disabled by default, bounded synthesis input, timeout/failure fallback and status API); initial orchestrator integration is now connected; evidence-citation prompts, human approval and model-backed integration tests remain pending.
- [x] Implement initial deterministic shared-core orchestration API with worker result aggregation, contract references, registry integrity gate and consolidated descriptive report; model-backed inference and source-provenance attachment remain pending.
- [x] Add initial shared-core worker registry and deterministic routing for supported workflow node types.
- [ ] Add worker registry versioning and a broader evaluation suite.
- [x] Add registry v1.0.0 manifest, deterministic SHA-256 digest, 550-profile/20-department integrity checks and registry status API; deeper per-worker behavioural evaluations remain pending.
- [x] Add append-only worker-scoped evidence memory with provenance and quality labels.
- [x] Add a prototype evidence-aware review gate for synthesis drafts. Source IDs must match a supplied registry before approval; this endpoint is stateless and does not authenticate reviewers or verify source authenticity. Persistent audit records and reviewer authorization remain pending.

Current boundary: worker routing invokes existing deterministic Python handlers. The 550 profiles are not independent models. Optional Ollama is a single shared, loopback-only summarization provider and is disabled by default; autonomous self-learning and brokerage execution remain disabled.
- [x] Add per-agent brain-context specifications for all 550 worker identities, including distinct specialization, memory namespace, context hash, and shared-core provider topology.
- [x] Add evaluated-feedback capture per worker and governed self-update proposals; updates remain pending review and require tests/rollback, with no autonomous model-weight training.
- [x] Implement bounded research-task execution with shared-core synthesis, per-agent context/memory, SQLite lifecycle persistence, quality-evaluation traceability, audit events, explicit dispatch, stale-task recovery, and supervisor reporting.\n- [ ] Add source retrieval with provenance-aware evidence grounding; current tasks use supplied data only.
- [ ] Implement autonomous research scheduling and cloud workspaces (currently not implemented).
- [ ] Implement evaluated learning loop with benchmark datasets, quality metrics, regression gates, and reviewed promotion of approved agent configuration changes.
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


## Analytical agent swarm milestone (2026-11-02)

Implemented the first per-agent brain and governed learning lifecycle scaffold. Every registered worker now has a distinct role prompt/context, specialty metadata, memory namespace and context hash while sharing one inference provider. Feedback can be recorded as worker-scoped validation memory. Agent configuration updates are proposals only, remain pending review, and are not automatically applied. This is not yet 550 continuously running autonomous cloud agents: bounded task execution exists, while cloud workspaces, scheduled research and a benchmark-driven learning/promotion loop remain future milestones. Paper trading and brokerage execution remain excluded.


- [x] Add guarded research report assembly that joins dataset metadata, chronological split checks, and classification metrics; no raw-data inspection or predictive-performance claim is made.

- [x] Add a best-effort Yahoo Finance historical daily adapter with adjusted-close preservation for return research.
- [x] Add a chronological ridge-regression next-day log-return experiment with train/validation/test separation and a zero-return baseline.
- [x] Add a CLI that fetches actual provider history and emits a source-stamped JSON report; empirical results must be generated by running it against a real symbol and must not be fabricated in CI.
