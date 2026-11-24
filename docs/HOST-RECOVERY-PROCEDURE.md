# ACC-030 — Host recovery procedure (preparation only)

Status: **BLOCKED** on a real authorized host. Everything below is operator
documentation; no systemd, crontab, Docker daemon or privileged operation was
executed in this repository. Local tests use fake shims and are contract tests.

## 1. Safe local preparation

```bash
python3 scripts/config_preflight.py --root .
python3 scripts/install_schedule.py plan --output-dir deploy/generated
python3 scripts/docker_volume_drill.py plan --source-volume market_mind_data --backup-dir ./backups
python3 scripts/host_recovery_plan.py --root .
```

`host_recovery_plan.py` is read-only: it aggregates the three plans, verifies
static config, and emits manual steps and rollback. It never calls systemctl,
crontab or Docker, and prints no environment values.

## 2. systemd installation (operator, root required)

1. Create `/etc/market-mind/market-mind.env` with mode **0600** containing
   `MARKET_MIND_DB`, `MARKET_MIND_DR_STATE_DIR`, retention, webhook and (if used)
   `MARKET_MIND_S3_*`. Never commit this file.
2. Generate and review files:
   `python3 scripts/install_schedule.py apply --apply --output-dir <review-dir>`.
   The generator writes `market-mind-backup.service`, `market-mind-backup.timer`
   (calendar-based with `Persistent=true`), `market-mind-restart-recovery.service`
   (with `[Install] WantedBy=multi-user.target`), `market-mind-backup.cron` and
   `install-plan.json`. Both services contain an active `EnvironmentFile=` line.
3. Install to `/etc/systemd/system/` manually, then:
   `systemctl daemon-reload && systemctl enable --now market-mind-backup.timer market-mind-restart-recovery.service`.
4. Verify `systemctl list-timers`, `systemctl status` and a successful backup
   manifest. Timer downtime catch-up is handled by `OnCalendar=daily` + `Persistent=true`.

## 3. cron alternative

Use the generated `market-mind-backup.cron` line. It sources the same 0600
EnvironmentFile (`set -a; . <file>; set +a`) before running `backup_scheduler.py run`.
Install with `crontab -e` on the authorized host; do not paste secrets into cron.
The restart-recovery service is still recommended for boot-time recovery.

## 4. Controlled restart and recovery drill

1. Enqueue a research task and let a worker claim it so a `running` row exists.
2. `kill -9 <worker-pid>`; wait one second.
3. `python3 scripts/service_restart_recovery.py run --stale-after-seconds 1`
   (or start the installed unit with that threshold). Default 900 s would delay
   the requeue and invalidate a short drill.
4. Expect: stale DR locks removed, `integrity_check=ok`,
   `requeued_interrupted_count=1`, `still_running_count=0`, `/api/ready` HTTP 200.
5. Capture the generated `restart-recovery-*.json` report and redacted journal lines.

## 5. Docker named-volume backup and restore (sub-drill)

The Compose stack uses the `market_mind_data` named volume. No backup bind mount
exists by default, so use the operator script with explicit arguments:

```bash
python3 scripts/docker_volume_drill.py plan --source-volume market_mind_data --backup-dir ./backups
python3 scripts/docker_volume_drill.py backup --apply --image <backend-image> \
  --source-volume market_mind_data --backup-dir ./backups
python3 scripts/docker_volume_drill.py restore --apply --image <backend-image> \
  --source-volume market_mind_data --target-volume market_mind_data-drill \
  --backup-dir ./backups --backup <backup-file>
```

The script mounts the source volume read-only, requires a **different** target
volume, refuses an existing target, verifies the SHA-256 sidecar, compares the
backup fingerprint with an in-container fingerprint of the restored volume, and
removes only the throwaway target. Success is `status=restored_and_verified`,
`comparison=matched`. It never runs `docker compose down -v`.

## 6. Aggregated evidence and rollback

```bash
python3 scripts/recovery_report.py --root ./backups --state-dir ./backups/.state
python3 scripts/host_recovery_plan.py --root .
```

Rollback: disable/stop generated units before removing them; restore the
pre-drill database from a separately verified backup if service state changed;
remove only the throwaway target volume, never the source. Do not restart or
modify production services outside an approved maintenance window.

The authoritative external procedure, expected results, required permissions,
evidence list and responsible operators are in
`docs/EXTERNAL-VERIFICATION-CHECKLIST.md` (EXT-02).
