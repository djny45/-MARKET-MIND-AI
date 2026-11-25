# 46-check acceptance status — production readiness

Generated from `docs/acceptance-inventory.json` plus the six public-ingress gates.
Status values: PASS (independently verified locally), BLOCKED (external evidence required), FAIL (none).

| # | ID | Check | Status | Evidence |
|---:|---|---|---|---|
| 1 | ACC-001 | Per-user authentication | PASS | `test_user_auth.py, test_user_auth_api.py` |
| 2 | ACC-002 | Four-role authorization | PASS | `test_authorization.py (SharedBearerPrivilegeTests)` |
| 3 | ACC-003 | Resource ownership | PASS | `test_authorization.py (DurableOwnershipTests)` |
| 4 | ACC-004 | Session CSRF/rotation/expiry | PASS | `test_user_auth.py, test_authorization.py` |
| 5 | ACC-005 | Strict environment validation | PASS | `test_env_validation.py` |
| 6 | ACC-006 | Trusted proxy and rate limiting | PASS | `test_rate_limit.py, test_distributed_rate_limit.py` |
| 7 | ACC-007 | Audit events and redaction | PASS | `test_audit_events.py` |
| 8 | ACC-008 | Frontend auth UI | PASS | `tests/ui/auth-panel.test.tsx` |
| 9 | ACC-009 | Role-aware navigation/access denied | PASS | `app.general-fixes.test.tsx` |
| 10 | ACC-010 | Observation screener | PASS | `coverage-tools.test.tsx` |
| 11 | ACC-011 | Coverage heatmap | PASS | `coverage-tools.test.tsx` |
| 12 | ACC-012 | Help dialog/news errors/watchlist states | PASS | `app.general-fixes.test.tsx, app.news.test.tsx` |
| 13 | ACC-013 | Responsive browser verification | PASS | `tests/e2e/responsive.spec.ts (9 pass); CI run 45367456403` |
| 14 | ACC-014 | 550 worker registry | PASS | `test_worker_registry.py, test_worker_skills.py` |
| 15 | ACC-015 | Skill allowlist and integrity | PASS | `test_skill_catalog.py, test_skill_integrity.py` |
| 16 | ACC-016 | Worker memory isolation and durable ownership | PASS | `test_worker_memory.py, test_worker_memory_ownership.py (3), test_authorization.py` |
| 17 | ACC-017 | Task ownership fencing | PASS | `test_analytical_agent_tasks.py, test_agent_supervisor.py` |
| 18 | ACC-018 | Supervisor lease-loss handling | PASS | `test_agent_supervisor.py (3 lease tests), test_supervisor_two_process_race.py (2-process single-host race)` |
| 19 | ACC-019 | Market-data provenance, staleness and provider health | PASS | `test_research_provenance_verification.py (6), test_market_data.py, test_provider_health.py` |
| 20 | ACC-020 | Historical research/backtesting | PASS | `test_run_historical_research_walk_forward.py, test_run_multi_symbol_research.py` |
| 21 | ACC-021 | Local backup, restore and recovery reporting | PASS | `test_recovery_drills.py (20), test_recovery_report.py (6); live: both SQLite files verified+restore-proven (scheduler-status.json)` |
| 22 | ACC-022 | Trivy CI full scope | PASS | `test_ci_workflow_config.py; GitHub Actions trivy-security job` |
| 23 | ACC-023 | Container/runtime integration | PASS | `GitHub Actions Docker Compose job` |
| 24 | ACC-024 | Imported execution code inert | PASS | `test_skill_integrity.py, test_mcp_server.py` |
| 25 | ACC-025 | S3 adapter contract and integrity (local) | PASS | `test_s3_offhost.py (2), test_s3_offhost_integration.py (8, fake S3)` |
| 26 | ACC-026 | Docker volume drill contracts and local integration | PASS | `test_docker_volume_drill.py (8, fake Docker shim; mock-based contract tests)` |
| 27 | ACC-027 | DR secret hygiene | PASS | `test_dr_secret_hygiene.py (3 tests)` |
| 28 | ACC-028 | Dual-auth browser integration | PASS | `test_frontend_auth_integration.py (1), tests/ui/api-client.test.ts (4)` |
| 29 | ACC-029 | Real cloud S3 restore using authorized infrastructure (EXT-01) | BLOCKED | `EXT-01: no cloud endpoint/bucket/credentials; local tooling and encrypted restore drill passed` |
| 30 | ACC-030 | Real host service installation, restart and recovery drill (EXT-02) | BLOCKED | `EXT-02: non-privileged recovery drill passed; no root/systemd/Docker host drill` |
| 31 | ACC-031 | Independent security review, penetration testing and formal sign-off (EXT-03) | BLOCKED | `EXT-03: internal audit passed; no independent reviewer or signed go/no-go` |
| 32 | ACC-032 | Host schedule installation scaffolding | PASS | `test_install_schedule.py (7)` |
| 33 | ACC-033 | Deployment config, TLS and ingress preflight | PASS | `test_config_preflight.py (7), test_ingress_config.py (14, 1 skip)` |
| 34 | OPS-001 | Portfolio research & performance analytics | PASS | `tests/ui/operations-panels.test.tsx` |
| 35 | OPS-002 | Risk analytics | PASS | `tests/ui/operations-panels.test.tsx` |
| 36 | OPS-003 | System health dashboard | PASS | `tests/ui/operations-panels.test.tsx` |
| 37 | OPS-004 | Provider health | PASS | `tests/ui/operations-panels.test.tsx` |
| 38 | OPS-005 | Audit & security events | PASS | `tests/ui/operations-panels.test.tsx` |
| 39 | OPS-006 | Backup & recovery status | PASS | `test_authorization.py, tests/ui/operations-panels.test.tsx` |
| 40 | OPS-007 | Settings & configuration | PASS | `tests/ui/operations-panels.test.tsx` |
| 41 | G1 | TLS issuance/scan | BLOCKED | scripts/ingress_gate_check.py: TLS template present; no real certificate/scan |
| 42 | G2 | network segmentation | BLOCKED | scripts/ingress_gate_check.py: loopback listeners, preflight pass; no host segmentation |
| 43 | G3 | ingress hardening | BLOCKED | scripts/ingress_gate_check.py: nginx limits/CSP pass; no deployed public ingress |
| 44 | G4 | independent security sign-off | BLOCKED | SECURITY-REVIEW-PACKAGE.md: internal audit passed; EXT-03 pending |
| 45 | G5 | licensed market-data/legal review | BLOCKED | LICENSED-DATA-INVENTORY.md: public `binance-public` bars in use (unlicensed public endpoints, not a licensed real-time feed); no legal approval for redistribution |
| 46 | G6 | host recovery drill | BLOCKED | container-recovery-evidence.json passed; EXT-02 pending |

Total: 46 checks — 37 PASS, 9 BLOCKED, 0 FAIL.

## Runtime verification (local, 2026-11-25)

Evidence gathered against the running stack, not from fixtures.

| Area | Result | Evidence |
|---|---|---|
| Backend suite | 1324/1324 OK, 1 skipped | `unittest discover backend/tests` on a clean worktree of HEAD (CI-identical) |
| Frontend unit | 10/10 node + 127/127 vitest, build clean | `npm test`, `npm run test:ui`, `npm run build` |
| Health latency | 50/50 ok; median 0.9 ms, p95 1.0 ms, max 41 ms | 50 sequential `/api/health` samples |
| Kill-and-recover (SIGKILL ×6) | all 6 services returned 0.8–2.5 s | `/tmp/mm-repair/drill-results.json` |
| Ledger reconciliation | `cash_mismatches=0/550`, `ledger_delta=0.0000000000` | replay of `paper_trades` |
| Paper DB backup | verified: 550 portfolios / 2239 positions / 9403 trades, FKs clean | `backups/scheduler-status.json` → `paper_trading_backup` |
| Market data | 148 live bars per symbol, fetch age ≤31 s, `source=binance-public` | `market_mind.db` |
| Exchange reachability | 5/5 HTTP 200 (Binance, Coinbase, Kraken, Binance.US, Bybit) | live curl |
| Auth / CSRF / Origin | unauth 401; missing/invalid CSRF 403; foreign Origin 403; no-Origin 403 | live requests via proxy origin |
| Token leak | 0 occurrences of `JUPYTERHUB_API_TOKEN` in any served file | grep across launcher/page/bundle |
| Dashboard a11y | `role=status`+`aria-live`, 3 table `aria-label`s, one `h1`, `lang=en` | real browser (Camoufox) DOM |
| Mobile ≤600 px | single-column grid, tables scroll internally, widest element 380 px | measured in browser |

### Defects found and fixed during this verification

Each was proven with the retained ledger before and after, never by assertion:

1. **SELL proceeds never credited** — `place_order` netted only `-(fee+slip)`. Now credits proceeds; regression tests in `SellAccountingTests`.
2. **Add-on cost basis excluded costs** — blended bare notional; now blends `quantity * exec_price`.
3. **Stop-loss/take-profit exited at $1.00** — `check_stop_loss_take_profit` omitted `price`, so fills used the `ref_price=1.0` fallback. Now passes the triggering market price.
4. **Stale marks on 540/550 agents** — the tick only re-priced the slice it traded. Added `mark_symbol_to_market()`; live-vs-mark drift is now 0.000% on all 2200 crypto positions.
5. **`paper_trading.db` was never backed up** — scheduler covered only `market_mind.db`, leaving 550 portfolios unprotected. Added a verified, restore-proven backup for the paper database.
6. **Drawdown contradicted the ledger** — `agent_0001` showed 40.24% while equity was above high-water (implied trough $311.96, ledger minimum $500.00). Repaired by ledger replay; worst drawdown is now 1.48% and a boundary test guards it.
7. **`status.py` hid dead services** — hardcoded 4 names; now enumerates `services.json`.
8. **JupyterHub API token embedded in served files** — removed from `launcher.ipynb` and the launcher HTML; the token has since rotated.

Known limitation, recorded rather than papered over: 39 legacy AAPL/MSFT/GOOG/TSLA positions from a superseded symbol config remain frozen at cost (`current_price == avg_entry`), so they contribute exactly 0.00 unrealized P&L. They have no live feed and cannot be independently priced.

## Score

- Private acceptance inventory: **37/40 = 92.5%**.
- Public ingress gates: **0/6 = 0%**.
- Overall production readiness: **37/46 = 80.43%** (40 acceptance items + 6 gates; 37 verified).
- Local operational reliability: **100%** of locally resolvable criteria.

No blocked item is marked PASS. External dependency details:
`docs/ACCEPTANCE-CLOSURE-EVIDENCE.md`.
