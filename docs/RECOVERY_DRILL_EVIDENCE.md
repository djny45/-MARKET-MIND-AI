# Recovery drill evidence — executed 2026-11-23

Re-verified independently at 2026-11-23T16:09Z from the same scripts
(`/tmp/opencode/run_dr_final.sh`, `/tmp/opencode/run_process_kill_drill.sh`):
backup restored with `comparison.status=matched`, `integrity=ok` on both
source and restored databases, equal table counts, retention prune kept the
newest 2 of 4 copies, one stale `restore.lock` removed, and the killed worker's
task was requeued (`requeued_interrupted_count=1`, `still_running_count=0`).
Fresh transcripts: `/tmp/drill-verify.log`, `/tmp/drill-kill-verify.log`.

Research-only platform. No live trading, wallet keys, signing or order routing
was enabled. All drills ran in isolated temporary directories, never against a
production database.

## 1. Backup / restore / retention / stale-lock drill

Runner: `/tmp/opencode/run_dr_final.sh` (reproducible shell script).
Full transcript: `/tmp/opencode/dr-drill-final.log`.
Base: repository `6c5fdcad`; Python 3.11.6 venv; timestamps UTC.

| Step | Command (abbreviated) | Result |
| --- | --- | --- |
| Fixture | `PYTHONPATH=.:./backend MARKET_MIND_DB=<tmp> python - … market_connect + enqueue_research_task` | PASS — 1 historical bar + 1 queued task |
| Backup | `python3 scripts/backup_orchestrator.py run --source … --destination-dir … --state-dir … --retention-days 0 --retention-count 5` | PASS — `market_mind-20261123T160453Z.db`, sha256 `f475705c697be9de9c1b417819cb3ef8886a3a1da4e7b2176c2afe1b856e0593` |
| Checksum | `sha256sum` vs `.sha256` sidecar | PASS — identical digests |
| Restore | `python3 scripts/restore_orchestrator.py restore --backup … --target … --state-dir …` | PASS — `comparison.status=matched`, schema version 1, no row-count differences |
| Integrity/parity | `dr_common.database_fingerprint` on source and restored DB | PASS — both `integrity=ok`, all table counts equal |
| Retention | `backup_orchestrator.py prune --retention-days 0 --retention-count 2` over 4 copies | PASS — 2 newest retained, 2 oldest pruned with sidecars removed |
| Stale lock/restart | `service_restart_recovery.py run --db … --state-dir … --stale-after-seconds 900` | PASS — 1 stale `restore.lock` removed, DB integrity ok, no dispatch performed |

## 2. Process-kill recovery drill

Runner: `/tmp/opencode/run_process_kill_drill.sh`.
Full transcript: `/tmp/opencode/process-kill-drill.log`.

| Time (UTC) | Action | Evidence |
| --- | --- | --- |
| 16:06:24Z | Created isolated DB and queued task `1358c63a-…` | `queued` |
| 16:06:25Z | Started worker that claimed the task and stalled in synthesis | worker PID 21457 |
| 16:06:28Z | `kill -9 21457` | `worker_killed=2026-11-23T16:06:28Z`, `running_after_kill=1` |
| 16:06:30Z | `service_restart_recovery.py run --stale-after-seconds 1` | `requeued_interrupted_count=1`, `still_running_count=0`, integrity ok |
| 16:06:30Z | Post-check | `queued_after_recovery=1`, `running_after_recovery=0` |

This is an isolated process-kill recovery drill, **not** a production-host
service restart. It verifies that a killed task executor leaves a recoverable
`running` record and that the recovery script requeues it without dispatching.

## 3. S3-compatible off-host prerequisite

`scripts/s3_offhost.py` implements a stdlib-only AWS SigV4 PUT/GET adapter with
credentials read **only** from `MARKET_MIND_S3_*` environment variables. It
supports `describe-config`, `upload`, `download` and `--dry-run`, and never
prints secrets. Tests: `backend/tests/test_s3_offhost.py` — fail-closed missing
credentials and secret-free output (2 tests PASS).

**Not performed:** real S3 upload or restore. No endpoint, credentials or
bucket exist in this environment; no credential was invented.

## 4. Not performed (external)

- Docker named-volume restore — `docker` binary absent.
- Host service restart / cron/systemd installation — no host init access.
- Real S3 restore — no credentials/endpoint.
- External TLS scan and independent pentest — operator/external work.

These remain operator-only and must not be reported as passed.
