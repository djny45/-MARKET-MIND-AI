# Final engineering audit (2026-11-24)

Baseline: branch `feature/phase3-external-prep`, head recorded in the final
report. Results below are from executed local checks on that tree; no external
infrastructure or independent approval is implied.

## 1. Backend and frontend architecture

- Backend: 121 application modules under `backend/app/`, FastAPI with optional
  deployment bearer, per-user sessions and durable SQLite ownership. 181 test
  modules under `backend/tests/`.
- Frontend: React 18 + Vite 6, 5 runtime / 15 dev dependencies; 127 Vitest tests
  across 21 UI files plus 10 `node:test` checks. Production build and both
  typecheck configurations pass.
- Versioned worker contracts for 10 workflow node types; single shared
  intelligence core, not 550 independent models.
- Architecture references: `docs/ARCHITECTURE.md`, `docs/FINAL_ARCHITECTURE.md`,
  `docs/AGENT-COUNCIL.md`, `docs/DEVELOPMENT.md`.

## 2. Database consistency and recovery

Executed evidence on the baseline:
- `unittest discover -s backend/tests -q` → 1,260 OK, 1 skipped (no nginx binary).
- Backup → checksum → clean restore → fingerprint parity, retention, stale-lock
  and process-kill recovery are covered by `test_recovery_drills.py` (20 tests),
  `test_backup_database.py`, `test_backup_wal_hygiene.py`.
- `scripts/recovery_report.py` aggregates real local artifacts; tests verify
  complete, incomplete, invalid-artifact, stale-pairing and CLI fail-closed cases (6 tests).
- Migration rollback path covered by `test_recovery_drills.py` and exercised
  locally on isolated DBs in the prior phase (`prepare → rollback → status`).
- Disk exhaustion fail-closed preflight: `test_dr_storage_failure.py` (4 tests).
- Real cloud S3, real Docker volume and host restart remain EXT-01/02 BLOCKED.

## 3. Agent registration and skill discovery

Runtime verification on this tree:

| Check | Result |
| --- | --- |
| Worker profiles | 550 (`list_workers`) |
| Departments / specialties | 20 / 28 (partial grid; 20×28=560 is **not** claimed as 550) |
| Allowlisted skills | 326 available, 0 malformed, 0 duplicate IDs |
| Research-pack sections | 300 uniquely titled entries in one pack SKILL.md |
| SKILL.md files | 115 total; 89 Vibe Trading files are unregistered reference material |
| Registry evaluation | `valid=True`, `errors=[]`, catalog 326 |
| Shared core | `shared_central_intelligence`; profiles are templates, `independent_models=False`, `broker_execution=False` |

Guards: `test_worker_registry.py`, `test_skill_catalog.py`,
`test_skill_integrity.py`, `test_research_inventory_claims.py` (3 tests) assert
that documentation counts cannot drift from runtime counts.

## 4. Research data provenance and provider failure

- Provenance labels (`live`/`delayed`/`historical`/`synthetic`) are bound to
  operator-attested sources; live/delayed claims without attestation are denied.
- Batch validation rejects non-finite values, duplicate/out-of-order/future bars
  and never imputes missing fields.
- `ProviderHealthRegistry` reports fresh/stale/unknown, degraded/unavailable and
  consecutive failures; synthetic data is never a healthy live feed.
- `/api/providers/status` reports `no_live_provider_configured`,
  `live_providers: []`, only a synthetic adapter available.
- Reproducibility: dataset/config digests and SHA-256 benchmark records; no
  predictive-skill or trading-profit claims.
- Evidence: `test_research_provenance_verification.py` (6),
  `test_market_data.py`, `test_provider_health.py`,
  `test_run_historical_research_walk_forward.py`.

## 5. Research-only boundary

`/api/health` returned HTTP 200 with
`{"status":"ok","mode":"research-only","paper_trading":false,"broker_execution":false}`.
No wallet keys, signing, broker routing or autonomous live trading paths were
added. Shadow orders remain log-only with `executed=false`; n8n import creates
inactive drafts only; the MCP catalog is a fixed allowlist without execution,
filesystem, network or brokerage tools. Imported execution code in
`third_party/` stays inert and is excluded from clean CI checkouts.

## 6. Findings and limits

- No new functional defect was found in this audit; 33 automated review findings
  from PR #102 were triaged and the genuine ones fixed before this package
  (`fix(audit)` commit). Remaining review comments are addressed or documented
  in the PR.
- Private verification remains 7/10 and public deployment 0/6: real cloud, host
  and independent security evidence are genuinely external.
- Single-host SQLite queue, in-process login counters and bounded Redis cooldown
  behaviour are documented limitations, not distributed deployments.
- No independent reviewer has signed off; ACC-031 remains BLOCKED.
