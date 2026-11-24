# Handover package EXT-02 — host service restart and recovery (ACC-030)

Status: **BLOCKED — no host execution here**. This environment has no root,
`docker`, `systemctl` or `crontab`; contract tests and container-only checks are
not host validation.

## Package contents

| File | Purpose |
| --- | --- |
| `../../HOST-RECOVERY-PROCEDURE.md` | Read-only runbook: units, environment file, restart drill, rollback |
| `../../EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-02 | Exact 8-step drill, evidence list and rollback |
| `../../EXTERNAL-ACCESS-REQUESTS.md` § EXT-02 | Ready-to-send host request and required permissions |
| `../../external-evidence/EXT-02.json` | Pending intake template (no evidence yet) |
| `../../../scripts/install_schedule.py`, `host_recovery_plan.py` | Read-only plan generation; `plan` writes nothing |
| `../../../scripts/service_restart_recovery.py`, `docker_volume_drill.py`, `config_preflight.py` | Operator commands and offline guards |
| `../../../scripts/external_evidence.py` | Fail-closed bundle validator |

## Permissions required from the host administrator

- sudo/root for `systemctl daemon-reload`, `enable --now`, `status`,
  `list-timers`, `journalctl`, and removal of generated units after the drill.
- Create `/etc/market-mind/market-mind.env` mode 0600 with `MARKET_MIND_DB`,
  `MARKET_MIND_DR_STATE_DIR`, retention and webhook settings; no inline secrets.
- crontab write access if the cron variant is used; Docker daemon access only
  for the optional named-volume sub-drill. Never delete the source volume.
- Production restart requires a maintenance window and a verified pre-drill DB.

## Entry / success / abort criteria

- Entry: `install_schedule.py plan` and `host_recovery_plan.py` produce plans
  with no writes and no `systemctl`/`crontab` invocation.
- Success: timer active; backup freshness `ok`; stale locks removed; killed
  `running` task requeued exactly once with `still_running_count=0`; DB
  `integrity_check=ok`; volume sub-drill `restored_and_verified` / `matched`;
  disposable volume removed.
- Abort: disable generated units, restore the pre-drill DB from a verified
  backup, remove only the disposable target volume.

## Closure

Operator completes the bundle with `systemctl status`/`list-timers`, redacted
journal excerpt, restart/recovery JSON, volume result, host identity and
operator name. Then `python3 scripts/external_evidence.py validate --bundle
<bundle>` must pass before ACC-030 may be changed to `verified`. Local
process-kill or container tests are explicitly not acceptable as this evidence.
