# Final validation evidence — production-readiness execution

Executed 2026-11-25 on the current working tree at `ae97d872` plus the audited
uncommitted changes. All results below were actually run. No external cloud
endpoint, credential, host reboot, independent reviewer or production ingress
was used or claimed.

## 1. Blocker status summary

| Blocker | Status | Basis |
| --- | --- | --- |
| EXT-01 cloud backup/restore | **BLOCKED** | No endpoint, bucket or scoped credentials. Local provider-independent config, encryption and restore tooling implemented and tested. |
| EXT-02 infrastructure recovery | **BLOCKED** | Non-privileged full-stack recovery drill passed; host systemd/Docker/reboot drill cannot be performed here. |
| EXT-03 independent security review | **BLOCKED** | Internal audit passed; no independent reviewer or signed go/no-go exists. |
| Full container reboot survival | **BLOCKED** | Simulated full process-tree restart passed; actual container/host boot hook requires privileged host access. |
| Public ingress six gates | **BLOCKED (0/6)** | Local portions validated; public ingress remains disabled. |

No blocked item is marked complete.

## 2. Backend suite

| Command | Result |
| --- | --- |
| `PYTHONPATH=backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q` | **1300 OK, 1 skipped** (final definitive run) |
| `... unittest tests.test_cloud_backup -q` | **8 OK** |
| `... unittest tests.test_ops_status -q` | **7 OK** |
| `... unittest tests.test_agent_supervisor tests.test_analytical_agent_tasks -q` | **68 OK** |
| `... unittest tests.test_s3_offhost tests.test_s3_offhost_integration -q` | **17 OK** |
| `... unittest tests.test_recovery_drills -q` (migration rollback, restore, stale locks) | included in full suite, PASS |

Final failures: **none**. Implementation-stage failures found and fixed: missing
`market_bars` fixture in the new backup drill, restore status string mismatch,
and PID-format assumption in the ops endpoint. All are covered by regression tests.

## 3. Frontend and CI

Node `v22.23.5` from `/home/jovyan/.nvm/versions/node/v22.23.5/bin`.

| Command | Result |
| --- | --- |
| `npm test` | **10/10 pass** |
| `npm run test:ui` | **21 files, 127/127 pass** |
| `npm run typecheck:test` | **exit 0** |
| `npm run build` | **Frontend production bundle created in frontend/dist** |
| `npx playwright test` (with cached Chromium library prefix) | **9 passed** |
| PyYAML `safe_load` on `.github/workflows/*.yml` | 3 valid: `quality.yml` 7 jobs, `github-pages.yml` 1, `n8n-skill-check.yml` 1 |
| `npm ci --dry-run --offline --ignore-scripts` | RC 0, lockfile in sync |

Frontend total: **146/146 pass**. GitHub-hosted CI jobs, Docker builds and
Trivy scans were not run locally and are not claimed.

## 4. Live platform

| Command | Result |
| --- | --- |
| `~/.market-mind-ops/health_check.py` | **20/20 PASS** |
| `~/.market-mind-ops/supervision/status.py` | **HEALTHY**, 4/4 services + supervision loop |
| `GET /api/health` / `/api/ready` | `research-only`, `paper_trading=false`, `broker_execution=false`, `status=ready` |
| Agent profiles / skills | 550 / 326 |
| MCP tools | 6 read-only; no broker/order/payment/transfer tool |
| `/api/ops/status` | 401 anonymous, 403 viewer, 200 admin |

## 5. Cloud backup configuration and encrypted restore

Implemented: `scripts/cloud_config.py` (vendor-neutral `MARKET_MIND_CLOUD_*`
contract mapped to the S3-compatible adapter) and `scripts/backup_crypto.py`
(AES-256-GCM authenticated encryption with plaintext SHA-256, tamper detection
and 0600 key-file support). `cryptography>=42,<51` added to runtime requirements.

| Test | Result |
| --- | --- |
| `cloud_config.py validate-config` with no config | **failed closed**: `missing_required_variables`, `encryption_not_configured` |
| `cloud_config.py validate-config` with complete dummy config | **ok**, no secret printed |
| `describe-config` | redacted, `credentials_exposed=false`, `values_exposed=false` |
| userinfo / base path / remote HTTP / bad key rejection | all failed closed |
| `backup_crypto.py encrypt → verify → decrypt` | round-trip byte-identical, integrity verified |
| tampered ciphertext | `integrity_failed`, exit 1 |
| `test_local_backup_encrypt_decrypt_and_restore_drill` | backup created → encrypted → decrypted → restored into clean target; `comparison=matched`; `PRAGMA integrity_check=ok` |
| Scheduler with local encryption key | `encryption.status=verified`, AES-256-GCM, plaintext digest recorded |
| Scheduler off-host destination | `not_configured` — correctly not claimed |

Cloud endpoint/bucket/credentials remain **none** per
`docs/EXTERNAL-ACCESS-REQUESTS.md`; no cloud restore was performed.

## 6. Backup and restore (live stack)

| Check | Result |
| --- | --- |
| Scheduled backup + SHA-256 sidecar + manifest | PASS |
| `restore_orchestrator.py verify` | `verified`, `comparison=matched` |
| Full restore into clean target (earlier live drill) | digest `93dc775a…` identical, FK violations `[]` |
| `/api/backup/status` | `ok`, fresh |
| Scheduler hard-kill | replacement restarted and produced a new verified backup |

## 7. Container recovery drill

Script: `~/.market-mind-ops/supervision/container_recovery_drill.py`
Evidence: `~/.market-mind-ops/container-recovery-evidence.json`

The drill hard-killed the supervision loop and all four services, cleared PID
files, and ran `bootstrap.sh`.

| Check | Result |
| --- | --- |
| Bootstrap after full kill | exit 0 |
| All four services healthy | true |
| Supervisor health | `healthy` |
| SQLite integrity before / after | `ok` / `ok` |
| Persistent worker-memory marker | present exactly once |
| Interrupted task | `task_requeued=1`, `task_claimed=1`, `task_completed=1`, one row |
| Duplicate task rows | none |
| Execution boundary | `research-only`, broker execution false |

This is a **non-privileged simulation**, not a host reboot or Docker restart.

## 8. Internal security audit

Evidence: `~/.market-mind-ops/internal-security-evidence.json`

| Check | Result |
| --- | --- |
| Anonymous `/api/workspaces`, `/api/ops/status` | 401 / 401 |
| Viewer admin-only routes | 403 / 403 |
| Admin admin-only routes | 200 / 200 |
| Security headers | CSP, `nosniff`, `DENY`, Referrer-Policy present |
| MCP allowlist | 6 tools, no forbidden symbols |
| Log secret scan | 0 matches |
| File permissions | 0600 on env, credentials, backup status |
| Config preflight | pass, 12/12, `values_exposed=false` |
| `pip-audit -r backend/requirements.txt` | **0 vulnerabilities / 39 dependencies** |
| `npm audit --omit=dev --audit-level=high --offline` | **0 vulnerabilities** |

No Critical/High internal finding. This is **not** an independent audit or
penetration test. Scope for an independent reviewer is in
`docs/SECURITY-REVIEW-PACKAGE.md`.

## 9. Public ingress gate validation

Evidence: `~/.market-mind-ops/ingress-gate-evidence.json`

| Gate | Public status | Local evidence |
| --- | --- | --- |
| G1 TLS issuance/scan | BLOCKED | TLS template present, preflight pass; no certificate issued/scanned |
| G2 network segmentation | BLOCKED | stack loopback-only, backend not host-published; host segmentation absent |
| G3 ingress hardening | BLOCKED | nginx limits/CSP/headers verified locally; no public ingress |
| G4 independent security sign-off | BLOCKED | internal audit passed; no independent reviewer |
| G5 licensed market-data/legal review | BLOCKED | `no_live_provider_configured`; legal review absent |
| G6 host recovery drill | BLOCKED | container drill passed; no systemd/Docker/root host drill |

`public_ingress_enabled: false`. No gate was marked PASS.

## 10. Completion calculation

| Scope | Count | Percentage |
| --- | --- | --- |
| Acceptance inventory | 37 verified / 40 | **92.5%** |
| Private research gates | 7 / 10 | **70%** |
| Public deployment gates | 0 / 6 | **0%** |
| Local operational reliability criteria | 31 / 31 | **100%** |
| Backend suite | 1300 OK + 1 skipped / 1301 | **99.92%** |
| Frontend suite | 146 / 146 | **100%** |
| Live health | 20 / 20 | **100%** |

**Overall production-readiness methodology:** public production requires all
40 acceptance items plus all 6 public ingress gates = 46 criteria. Verified:
37 acceptance items and 0 public gates. Therefore **37/46 = 80.43%**. This is
conservative: EXT-03 is counted once as an acceptance item and once as a public
gate. The remaining 9 criteria require genuine external evidence.

Local reliability criteria: supervisor start, dispatch, interrupted requeue,
hard-kill recovery, 32.6s lease grace, backend auto-restart, backup-scheduler
auto-restart, graceful shutdown, cold start, idempotent bootstrap, backup
sidecar, manifest, retention, interval, scratch restore, full restore, digest
and FK match, truthful backup status, S3 adapter tests, off-host hook,
cloud config validation, AES-GCM encryption, tamper detection, encrypted
restore drill, status CLI, status API roles, log secret scan, 0600 perms,
loopback listeners, full-stack recovery drill, and internal audit/dependency
scans.

## 11. Outstanding external dependencies

1. EXT-01: endpoint, bucket, region, scoped access/secret keys, isolated host.
2. EXT-02: root/systemd/Docker host, 0600 `/etc/market-mind/market-mind.env`,
   maintenance window, host recovery evidence.
3. EXT-03: independent reviewer, signed rules of engagement, test identities,
   scanner/TLS outputs, signed report and go/no-go.
4. Real TLS certificate issuance/scan and public ingress deployment.
5. Licensed market-data provider and legal review.
6. Host boot hook to run `bootstrap.sh` after a real reboot.

## 12. Final acceptance execution (current cycle)

Additional locally resolvable work completed in this cycle:

| Item | Evidence | Result |
| --- | --- | --- |
| Unprivileged login/boot hook | `~/.market-mind-ops/shell-hook-evidence.json` | PASS — after killing loop + all 4 services, one `bash -ic true` restored HEALTHY |
| Licensed-data inventory | `docs/LICENSED-DATA-INVENTORY.md` | inventory complete; legal review remains BLOCKED |
| EXT evidence requirements | `docs/ACCEPTANCE-CLOSURE-EVIDENCE.md` | all 9 open checks mapped to exact artifacts/checks |
| Reusable ingress validator | `scripts/ingress_gate_check.py`, `tests/test_ingress_gate_check.py` | 6/6 gates BLOCKED, `public_ingress_enabled=false`; 3 tests OK |
| Authoritative 46-check table | `docs/ACCEPTANCE-46-STATUS.md` | 37 PASS, 9 BLOCKED, 0 FAIL |

Commands re-run in this cycle:

| Command | Result |
| --- | --- |
| `PYTHONPATH=backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q` | **1300 OK, 1 skipped** |
| `npm test` | 10/10 |
| `npm run test:ui` | 127/127, 21 files |
| `npm run typecheck:test` | exit 0 |
| `npm run build` | production bundle created |
| `npx playwright test` | 9 passed |
| `health_check.py` | 20/20 |
| `config_preflight.py --root .` | pass, 12/12 |
| `ingress_gate_check.py` | 0/6 public gates PASS, ingress disabled |
| `external_evidence.py audit` | 40 items, 37 verified, 3 blocked, 92.5% |
| `npm audit --omit=dev --audit-level=high --offline` | 0 vulnerabilities |
| `pip-audit -r backend/requirements.txt` | 0 vulnerabilities |
| log secret scan | 0 matches |
| `stat` on env/credentials | 0600 |

No FAIL status in the final run. All 9 open checks remain BLOCKED pending
genuine external evidence.

## 13. Fresh validation pass — 2026-11-25T04:30:05Z

No implementation changes were made in this pass. Every check below was re-run
against the current working tree after the earlier implementation cycle.

| Command | Fresh result |
| --- | --- |
| `PYTHONPATH=backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q` | **1300 OK, 1 skipped, 0 failures** (`~/.market-mind-ops/fresh-backend.log`) |
| `npm test` | 10/10 pass |
| `npm run test:ui` | 127/127, 21 files |
| `npm run typecheck:test` | exit 0 |
| `npm run build` | production bundle created |
| `npx playwright test` | 9 passed |
| `health_check.py` | 20/20 |
| `config_preflight.py --root .` | pass, 12/12 |
| `ingress_gate_check.py` | 0/6 public gates PASS, `public_ingress_enabled=false` |
| `external_evidence.py audit` | 40 items, 37 verified, 3 blocked, 92.5% |
| `npm audit --omit=dev --audit-level=high --offline` | 0 vulnerabilities |
| `pip-audit -r backend/requirements.txt` | 0 vulnerabilities |
| log secret scan | 0 matches |
| env/credentials `stat` | 0600 / 0600 |
| stack listeners | `127.0.0.1:8000`, `127.0.0.1:8080` |
| `restore_orchestrator.py verify --backup market_mind-20261125T041354Z.db` | `verified`, comparison `matched`, FK ok |
| `restore_orchestrator.py restore --backup ... --target /tmp/opencode/mm-restore-fresh` | `restored_and_verified`, digest match, `PRAGMA integrity_check=ok`, 13 tables |
| `container_recovery_drill.py` | passed; integrity `ok`; `task_requeued=1`, `task_completed=1`; all 4 services healthy |

Failed tests in the fresh pass: **none**. External blockers remain exactly as
listed in section 11; none were closed without genuine evidence.
