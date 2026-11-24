# Backup / Recovery Drill — evidence-based (2026-11-23)

Research-only platform. No live trading, wallet keys, signing or order routing
was enabled, configured or exercised in any drill.

## Environment note

The historical 2026-11-22 drill ran in a copied target
(`/tmp/opencode/MARKET-MIND-AI-target`) with a synthetic SQLite fixture because
the runtime DB lacked `market_bars`. Its raw log and fixture are no longer
present in this container, so those historical outputs are **not independently
re-verifiable here**; they remain a recorded narrative, not new evidence.

## Verified in this audit (commands and results)

```
PYTHONPATH=.:./backend python -m unittest backend.tests.test_recovery_drills -q
Ran 14 tests ... OK
```

Note: this file's test class now contains 14 tests; the historical drill
document recorded 19 tests across two modules. The authoritative count for the
current tree is in `FINAL_TEST_RESULTS.md`.

A real defect was found and fixed: `DrLock.stale_count()` called `_read_pid()`
on its own lock path instead of the iterated path. With a live `backup.lock`
present it would not clear other stale locks; with a dead `backup.lock` it could
delete another process's live lock. A regression test now creates a live
`backup.lock` and a dead `restore.lock` and asserts only the dead one is
removed. This directly protects `scripts/service_restart_recovery.py`.

Read-only checks also succeeded: `python3 scripts/backup_scheduler.py config`,
`cron-line`, `systemd`, and `--help` on each DR orchestrator.

## Capability status

| Capability | Status |
| --- | --- |
| Backup integrity (`PRAGMA integrity_check`, `market_bars` required) | Implemented, unit-tested |
| SHA-256 sidecars and tamper rejection | Implemented, unit-tested |
| Retention (age + count, sidecars pruned) | Implemented, unit-tested |
| Generic off-host hook + stdlib S3 adapter | Implemented, unit-tested; local fake-S3 round-trip PASS, real cloud target not configured |
| Clean restore and SQLite integrity/row-count parity | Implemented, unit-tested |
| Stale-lock recovery | Implemented; **bug fixed in this audit** with regression test |
| Restart recovery / stale task requeue (no dispatch) | Implemented, unit-tested |
| Migration rollback | Implemented for simulated failures; **no real migration runner** |
| Incident webhook with redacted payloads | Implemented, loopback-tested |
| cron/systemd generation | Implemented; installation NOT performed |
| Docker named-volume restore | Operator script `scripts/docker_volume_drill.py` (plan default, `--apply` required) with fake-Docker tests; real Docker host run NOT performed |
| Real S3 target | Adapter implemented; real endpoint/bucket/credentials not configured |
| Production process-kill drill | NOT RUN; procedure in `docs/PUBLIC-EXPOSURE-HARDENING.md` |

## Operator-only work (not claimed as tested)

- Install cron/systemd timers on the host.
- Restore a Docker named volume (`market_mind_data`).
- Configure and verify a real S3-compatible target (see
  `docs/PUBLIC-EXPOSURE-HARDENING.md` §6).
- Roll back a real application migration (only a `schema_migrations` version
  table exists).
- Run the host restart and process-kill drills (§7 of the same document).

## Residual risks

`MARKET_MIND_BACKUP_UPLOAD_CMD` executes an operator-supplied command (no shell)
and `MARKET_MIND_INCIDENT_WEBHOOK_URL` accepts any operator-supplied HTTP(S)
URL: both are trust-boundary inputs, not application vulnerabilities.
`retention_days=0` without a count keeps all backups; configure both explicitly.
