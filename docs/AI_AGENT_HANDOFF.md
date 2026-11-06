# AI Agent Handoff Contract

This document defines how external AI coding agents can extend MARKET-MIND-AI without duplicating components or weakening its research-only boundaries.

## Product boundary

MARKET-MIND-AI is a market-research workspace. Agents may inspect supplied or authorized market data, compute indicators, summarize evidence, annotate charts, and produce reproducible reports. Do not implement broker credential collection, order routing, live order placement, order modification/cancellation, or unattended real-money execution. Do not describe hypothetical or simulated output as live trading.

## Repository-first workflow

1. Read `AGENTS.md`, `PROJECT_STATUS.md`, and the relevant subsystem documentation before editing.
2. Inspect the existing implementation and tests; reuse existing endpoints, components, schemas, and utilities.
3. State the exact files to change and the behavior being added before making a large change.
4. Keep changes scoped to one subsystem and avoid unrelated refactors.
5. Add or update tests for every behavior change, including invalid input and failure paths.
6. Run the applicable local checks when the environment permits. If not run, say so explicitly.
7. Commit to the task branch; do not silently push to or merge into `main`.
8. Report the commit SHA, files changed, checks run, and known limitations.

## Shared research result contract

Research modules should return a structured record with these fields when applicable:

- `schema_version`: versioned contract identifier.
- `task_id`: stable task identifier.
- `agent_id`: worker/profile identifier, not a claim of an independent model.
- `symbol` and `interval`: instrument and timeframe context.
- `status`: `completed`, `partial`, `failed`, or `not_run`.
- `source`: provider, imported file, or fixture identifier.
- `retrieved_at`: timezone-aware timestamp for data retrieval.
- `data_status`: `historical`, `delayed`, `synthetic`, `manual`, or `unknown`.
- `method`: indicator, analysis method, and version where available.
- `findings`: concise evidence-linked observations.
- `warnings`: missing data, stale data, assumptions, and other limitations.
- `errors`: sanitized error details; never include secrets or full environment values.

Do not fabricate missing provenance. Unknown values should remain explicitly unknown.

## Chart annotation contract

Chart annotations are research artifacts, not orders. Every annotation should include:

- `id`, `kind`, and `label`;
- `symbol` and `interval`;
- `created_at` and `created_by`;
- `origin`: `user`, `indicator`, or `research_agent`;
- optional price/time coordinates;
- optional linked `task_id` and evidence/source references;
- `description` and `limitations`.

Distinguish user-entered levels from indicator-derived values and agent interpretations using both label and visual styling. Do not label annotations as buy/sell instructions or connect them to a broker action.

## Agent task lifecycle

Use explicit states where supported:

`queued → running → completed | partial | failed | cancelled`

A task should expose its ID, timestamps, input summary, worker/profile, status, output reference, and sanitized error. Retries must not create duplicate persisted results accidentally. Background-task status must not be presented as durable distributed execution unless persistence and recovery actually exist.

## Integration checklist

- [ ] Existing code inspected; no duplicate chart/API/module created.
- [ ] Request and response schemas documented.
- [ ] Input validation and size limits included.
- [ ] Source/freshness/status metadata retained end-to-end.
- [ ] Research-only boundary preserved.
- [ ] No API keys, tokens, or secrets in source, logs, fixtures, or frontend bundles.
- [ ] Tests cover success, malformed input, and relevant failure cases.
- [ ] Frontend distinguishes real historical data, user input, and synthetic fixtures.
- [ ] CI result and commit SHA included in handoff report.

## Agent completion report

Return a concise report containing:

1. Summary of implemented behavior.
2. Files changed.
3. Commit SHA and branch.
4. Tests/checks actually executed and their results.
5. Known gaps and next integration dependency.

A task is not complete merely because code was generated. It is complete when the change is committed, its contract is documented, and its applicable checks have been verified or clearly marked as not run.
