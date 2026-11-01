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
- [x] Add source-isolated chronological evaluation dataset manifests with SHA-256 provenance digests, explicit embargoes, and invalid-data gates.\n- [ ] Add model/strategy evaluation framework with leakage, survivorship, revision, and selection-bias controls.

## Phase 4 — Intelligence and workflow canvas
- [x] Version the deterministic worker contract and expose contract version in capabilities and dispatch responses.
- [x] Add bounded deterministic worker dispatch with explicit capability authorization and a capability-status API.
- [x] Add a typed evidence-first research aggregation API with market coverage, source references, quality labels and disagreement reporting.
- [x] Add provenance-gated cross-market research round assembly and read-only API.\n- [x] Add bounded worker-to-worker delegation through caller-authored task DAGs.\n- [x] Add central deterministic coordinator combining worker delegation and evidence-first market synthesis.
- [x] Add deterministic worker capability smoke-evaluation suite and read-only evaluation API.\n- [x] Add fixed analytical reference-vector correctness benchmarks and a read-only evaluation API.\n- [ ] Add broader property-based, independent-library, and longitudinal benchmark coverage.\n- [ ] Add worker registry governance.
- [x] Add isolated append-only worker research memory with source references and pending-review status.\n- [x] Add explicit human-reviewed promotion into shared knowledge with source-reference requirements.\n- [ ] Add authenticated reviewer identity and multi-user authorization before deployment.
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


## Human-reviewed shared knowledge and central coordination

- Worker memory can be reviewed through `POST /api/workers/{worker_id}/memory/{memory_id}/review`. Approval copies a note into the shared knowledge store; rejection leaves it out. The reviewer identity is recorded as a supplied label and is not authenticated by an identity provider.
- `GET /api/knowledge/shared` returns approved entries only.
- `POST /api/intelligence/coordinate` combines bounded worker delegation and caller-supplied findings into one evidence report. It is deterministic, not an autonomous central AI model.

## Data-source licensing readiness

- `GET /api/providers/catalogue` lists the existing manual CSV and synthetic fixture paths plus a not-yet-implemented licensed vendor adapter category.
- No commercial vendor or exchange feed is activated. Before adding one, document the contract, venue/instrument entitlements, permitted storage, retention, redistribution and display rights, credential handling, and connector validation.


## Delegation and central coordination contracts

- `POST /api/workers/delegate` is the existing sequential delegation endpoint. It accepts up to 50 caller-supplied task records, requires explicit worker IDs and operations, and only allows dependencies on earlier completed tasks.
- `POST /api/intelligence/coordinate` is the central deterministic control plane. It accepts a bounded worker task DAG and numeric input series, routes operations to authorized deterministic worker capabilities, and combines execution with the supplied evidence brief. It requires each requested market to have at least one distinct non-synthetic source reference before returning `ready_for_human_review`.
- The coordinator does not autonomously generate tasks or findings, authenticate source claims, invoke an LLM, retrieve data, or execute orders.

## Shared knowledge governance

Worker notes remain isolated and pending review by default. The `POST /api/workers/{worker_id}/memory/{memory_id}/review` endpoint requires an explicit approve/reject decision and reviewer label. Approval requires at least one source reference and rejects synthetic fixture notes; promotion and the worker-memory status update occur in one SQLite transaction. The reviewer label is caller-supplied, not authenticated, so the endpoint must remain behind a trusted local boundary until authentication and authorization are implemented. The `GET /api/knowledge/shared` endpoint returns approved entries only. Human review does not independently authenticate the source or establish factual truth.

## Historical and live data licensing

The `GET /api/providers/catalogue` endpoint is a metadata-only readiness register. The repository supports user-supplied historical CSV imports and synthetic fixtures; no licensed vendor historical or streaming connector is enabled. Before activating a source, record the legal entity and contract, permitted venues/instruments, historical depth, streaming entitlement, display and non-display rights, derived-data rights, retention limits, redistribution restrictions, geographic limits, credential handling, and vendor audit obligations. Connector activation remains disabled until contract review and technical acceptance checks are complete. Never label an imported file or feed as licensed merely because it is reachable.


## Provider entitlement manifest gate

The `POST /api/providers/validate-entitlement` endpoint validates an operator-supplied manifest for markets, historical/live modes, expiry, and declared display, non-display, storage, derived-data, redistribution, and retention rights. A complete manifest is only eligible for manual legal and technical review. It does not authenticate the contract, validate credentials, or activate a connector. Live and historical licensed connectors remain unimplemented pending an actual vendor agreement and approved integration.


## Historical evaluation dataset manifests

`GET /api/research/evaluation-manifest` produces deterministic chronological development, validation and holdout partitions for each source independently. It includes a canonical SHA-256 digest, partition boundaries, observation counts and explicit embargo intervals. This is dataset preparation only; no model fitting, parameter tuning, strategy backtest or performance claim is made. Embargoes are not a complete remedy for look-ahead, survivorship, revision or selection bias.
