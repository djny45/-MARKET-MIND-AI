# External verification checklist (2026-11-24)

Scope: the three acceptance checks that **cannot** be closed in this
environment. Nothing below has been executed here. No credentials, endpoints,
hosts or permissions were invented. Local mock/fake tests prove command
contracts only and must never be recorded as PASS for these checks.

| ID | Check | Status | Acceptance inventory row |
| --- | --- | --- | --- |
| EXT-01 | Real cloud S3 restore using authorized infrastructure | BLOCKED | `ACC-029` |
| EXT-02 | Real host service installation, restart and recovery drill | BLOCKED | `ACC-030` |
| EXT-03 | Independent security review, penetration testing and formal sign-off | BLOCKED | `ACC-031` (also a public-deployment gate) |

Note: the former "Docker volume restore on a real host" item is folded into
EXT-02 as a sub-drill; it is not a separate private acceptance item. This
removes the duplicate that previously counted the same external gap twice.

---

## EXT-01 — Real cloud S3 restore

**Required infrastructure and permissions**
- S3-compatible endpoint with a dedicated bucket; versioning, object lock and
  server-side encryption enabled; public access blocked.
- Scoped credentials (`s3:PutObject`, `s3:GetObject`, `s3:ListBucket`) supplied
  only through `MARKET_MIND_S3_*` environment variables from a 0600 EnvironmentFile.
- Authorized private host with Python 3.11+, this checkout, and a writable
  isolated restore directory. No production database is touched.

**Exact test procedure**
1. `python3 scripts/s3_offhost.py describe-config --dry-run` — confirm the
   endpoint/bucket/region/prefix are present and `credentials_exposed=false`.
2. Create a verified local backup with
   `python3 scripts/backup_orchestrator.py run --source <db> --destination-dir <dir> --state-dir <state>`.
3. Upload with `MARKET_MIND_BACKUP_UPLOAD_CMD='python3 scripts/s3_offhost.py upload --file {backup} --key {name}'`
   and `backup_orchestrator.py retry-upload` if needed.
4. Download to a **new** path with `s3_offhost.py download --file <isolated>/restored.db --key <key>`.
5. `sha256sum` the local and downloaded files; verify against the `.sha256`
   sidecar and the backup manifest.
6. `python3 scripts/restore_orchestrator.py verify --backup <downloaded> --state-dir <state>`
   then `restore --target <clean-isolated-dir>`; compare fingerprints and row counts.
7. `python3 scripts/recovery_report.py --root <dir>` and confirm
   `status=evidence_complete`, `freshness=ok`, restore comparison `matched`.

**Expected result**
- All commands exit 0; SHA-256 parity; restore comparison `matched`;
  `integrity=ok`; no secret value in any stdout, manifest or report.

**Evidence to capture**
- Redacted command transcripts, sidecar and manifest files, restore report,
  restart/recovery report, `recovery_report.py` JSON, object key and bucket
  name (not credentials), timestamp and operator identity.

**Rollback**
- Do not overwrite the live database. Discard the isolated restored copy.
- If a restore was applied to a service database, stop writes and restore the
  separately verified pre-drill backup; revoke/rotate the drill credentials.
- Never run `docker compose down -v` or delete the source volume.

**Responsible external operator**
- Cloud infrastructure owner with IAM authority and the host operator who owns
  the private database. Sign-off required from both.

---

## EXT-02 — Real host service installation, restart and recovery drill

**Required infrastructure and permissions**
- Authorized Linux host with `systemd` or `crontab`, sudo/root, and a 0600
  EnvironmentFile containing `MARKET_MIND_DB`, `MARKET_MIND_DR_STATE_DIR`,
  retention and webhook settings (no inline secrets in unit files).
- Docker engine and a disposable named volume if the volume sub-drill is included.
- Generated scaffolding from `scripts/install_schedule.py`; reviewed diff.

**Exact test procedure**
1. `python3 scripts/install_schedule.py plan --output-dir <review-dir>` — verify
   no writes and no `systemctl`/`crontab` invocation.
2. `apply --apply --output-dir <review-dir>`; review the generated service,
   timer, restart-recovery unit and crontab line. Install manually on the host.
3. `systemctl daemon-reload && systemctl enable --now market-mind-backup.timer`;
   confirm `systemctl list-timers` and one successful backup manifest.
4. Kill the supervisor/executor process with `kill -9` during a queued task;
   run `python3 scripts/service_restart_recovery.py run` (or let the unit run).
5. Check `/api/ready` (200), `PRAGMA integrity_check`, and that the killed
   `running` task was requeued exactly once with `still_running_count=0`.
6. Volume sub-drill: `docker_volume_drill.py plan`, then `backup --apply` and
   `restore --apply` into a **different** disposable volume; compare fingerprints.
7. Capture `recovery_report.py` after the drill.

**Expected result**
- Timer active; backup fresh (`freshness=ok`); stale locks removed; interrupted
  task requeued without dispatch; database integrity `ok`; restore comparison
  `matched` for the volume sub-drill; throwaway volume removed.

**Evidence to capture**
- `systemctl status/list-timers` output, redacted journal excerpts, PID/kill
  timestamps, restart report JSON, `recovery_report.py` JSON, volume names
  (source and disposable target), host identity and operator name.

**Rollback**
- `systemctl disable --now` the timer/service and remove generated units if the
  drill fails. Restore the pre-drill database from a verified backup. Remove
  only the disposable target volume; never the source volume.

**Responsible external operator**
- Host/system administrator with root and the service owner. Production restart
  requires an explicit maintenance window.

---

## EXT-03 — Independent security review, penetration testing and sign-off

**Required infrastructure and permissions**
- Staging deployment reachable through the reviewed TLS ingress, with test
  identities for each role and written rules of engagement/rules of scope.
- Independent reviewer or testing firm with no production write credentials.
- Scanners (dependency, container, TLS/SSL) and a signed report template.

**Exact test procedure**
1. Review auth/session boundaries: bearer-only and dual-auth modes, CSRF and
   Origin enforcement, role hierarchy, ownership and unknown-resource denial.
2. Exercise login throttling/lockout, rate-limit denials and audit events;
   confirm no credentials or tokens appear in logs, manifests or webhook bodies.
3. Test TLS configuration (protocols, ciphers, HSTS), ingress rate/connection
   limits, forwarded-proto hop count and network segmentation (no backend host
   ports, loopback-only published ports).
4. Perform authorized authenticated and unauthenticated penetration tests;
   log each finding with severity and reproduction.
5. Retest remediations and issue a formal go/no-go decision.

**Expected result**
- No open Critical/High findings; Medium findings have documented acceptance;
  100% of planned scope executed; signed go/no-go statement.

**Evidence to capture**
- Signed assessment report, scope and rules of engagement, finding IDs with
  remediation and retest dates, scanner outputs, TLS scan result, reviewer
  names/credentials and decision date.

**Rollback**
- If any Critical/High finding is open, keep public ingress disabled and the
  service in research-only private mode; remediate and retest before re-review.
  No rollback of code is required unless a finding identifies a regression.

**Responsible external operator**
- Independent security lead / penetration-test provider and the repository
  owner who accepts or rejects the final sign-off.

---

## Recording the result

Only after an external operator executes the procedure and supplies evidence
may the corresponding acceptance row change from `blocked` to `verified`, with
the exact procedure URL, evidence location and operator identity. Mock, fake or
simulated tests must not be used as evidence for EXT-01, EXT-02 or EXT-03.
