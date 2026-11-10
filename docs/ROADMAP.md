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
  - [x] Add research-only binary classification metric summaries and majority-class baseline comparisons.
- [x] Add split-level binary research evaluation aggregation; caller-supplied labels/predictions only, not model-performance evidence.
  - [x] Add research-only dataset metadata gate; it does not inspect underlying bars or establish evaluation validity.

## Phase 4 — Intelligence and workflow canvas
- [ ] Define complete typed specialist-worker input/output contracts.
- [x] Add versioned v1.0.0 contract definitions and runtime shape validation for supported workflow node types; detailed domain schemas and mandatory provenance enforcement remain pending.\n  - [x] Validate optional supplied source provenance (non-empty source, timezone-aware ISO-8601 retrieval timestamp, and quality status); provider-wide mandatory provenance remains pending.
  - [x] Propagate validated provenance metadata into findings and report coverage metrics (coverage, unprovenanced nodes, declared source counts, and quality-status counts); these metadata checks do not prove source authenticity or claim entailment.
- [ ] Build central research orchestrator with model-backed inference and evidence-grounded synthesis.
- [x] Add optional single-core local Ollama provider boundary (loopback-only, disabled by default, bounded input, timeout/failure fallback and status API); evidence-citation prompts, human approval and model-backed integration tests remain pending.
- [x] Implement initial deterministic shared-core orchestration API with worker result aggregation, contract references, registry integrity gate and descriptive report; model-backed inference and source-provenance attachment remain pending.
- [x] Add initial shared-core worker registry and deterministic routing.
- [ ] Add worker registry versioning and broader evaluation.
- [x] Add registry v1.0.0 manifest, SHA-256 digest and 550-profile/20-department integrity checks; deeper worker behavior evaluations remain pending.
- [x] Add append-only worker-scoped evidence memory with provenance and quality labels.
- [x] Add prototype evidence-aware review gate; source IDs must match a supplied registry. Reviewer authentication and persistent audit remain pending.
- [x] Add conservative evidence traceability audit: unknown reference reporting, URL/declared-group source grouping, and explicitly keyed stance-disagreement candidates with human-review status. This is heuristic metadata analysis, not source authenticity, entailment, or truth verification.
- [x] Add bounded per-agent task submission, SQLite task persistence, supervisor dispatch, recovery, retry/cancel controls, and task audit endpoints; shared-core synthesis is configuration-dependent and source retrieval is not automatic. This is not a durable distributed queue or 550 always-on processes.
- [x] Add bounded autonomous descriptive research over injected adapters plus stored-data and synthetic-fixture API routes; scheduled execution, cloud workspaces, and always-on autonomous loops remain unimplemented.
- [ ] Implement evaluated learning loop with benchmark datasets, quality metrics, regression gates, and reviewed promotion.
- [x] Build the initial React Flow visual workflow editor and DAG execution path for supported node types; the full 550-profile catalogue is not equivalent to 550 executable workflow handlers.
- [x] Add initial provenance coverage and metadata-quality counts to orchestrated research reports; full source authenticity, claim entailment, and end-to-end explainability remain pending.

Current boundary: worker routing invokes deterministic Python handlers. The 550 profiles are not independent models. Optional Ollama is a single shared, loopback-only summarization provider and is disabled by default; autonomous self-learning and brokerage execution remain disabled.

## Phase 5 — Reliability and governance
- [x] Add historical evidence export, SHA-256 verification, batch verification, and before/after comparison with provenance.
- [x] Add SQLite ingestion audit events and source/status data-lineage views.
- [x] Add SQLite backup with integrity verification and SHA-256 digest.
- [x] Add safe SQLite restore with source/target verification, atomic replacement, and overwrite protection.
- [x] Add CI backup/restore round-trip test inside production API image.
- [x] Add private Docker deployment documentation, resource limits, dropped Linux capabilities, no-new-privileges, and rotating container logs.
- [ ] Add observability, performance profiling, and load tests.
- [ ] Add security review and dependency/licence inventory.
- [ ] Complete host-specific backup/restore drills, retention policy, migration rollback, and incident procedures.
- [ ] Add authentication/authorization and TLS ingress before public deployment.

## Acceptance criteria

A module is considered implemented only when it has:
1. A documented interface and configuration.
2. Automated tests, including failure and missing-data cases.
3. Data provenance and timestamp handling where relevant.
4. Security and licence review.
5. User-facing documentation and known limitations.

## Analytical agent swarm milestone (2026-11-02)

Implemented the first per-agent brain and governed learning lifecycle scaffold. Every registered worker has a distinct role prompt/context, specialty metadata, memory namespace and context hash while sharing one inference provider. Feedback can be recorded as worker-scoped validation memory. Agent configuration updates are proposals only and remain pending review. This is not 550 continuously running autonomous cloud agents: independent task execution, cloud workspaces, scheduled research and benchmark-driven learning/promotion remain future milestones. Brokerage execution remains excluded.

- [x] Add guarded research report assembly joining dataset metadata, chronological split checks and classification metrics; no raw-data inspection or predictive-performance claim.
- [x] Add best-effort Yahoo Finance historical daily adapter with adjusted-close preservation.
- [x] Add chronological ridge-regression next-day log-return experiment with train/validation/test separation and zero-return baseline.
- [x] Add CLI for real source-stamped historical reports; empirical results must not be fabricated in CI.
- [x] Validate research-quality and offline-benchmark baselines against supported metric allowlists and numeric ranges.
- [x] Validate baseline schemas before processing benchmark cases or claims.
- [x] Disclose skipped offline benchmark comparisons; skipped comparisons are not evidence of a pass.
