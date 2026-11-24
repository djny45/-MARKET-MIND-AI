# Stacked PR review report (final cycle)

Review date: 2026-11-24. Scope: PRs #100, #102 and #103 as stacked branches
(`main` ← #100 ← #102 ← #103). All three remain OPEN and MERGEABLE; none was
merged automatically.

| PR | Head SHA | Diff | CI run | Result |
| --- | --- | --- | --- | --- |
| #100 | `2f3db51dc79a` | 11 commits, 39 files | [45346939072](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45346939072) | all 6 jobs PASS |
| #102 | `e69530045225` | 8 commits, 21 files | [45353077146](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45353077146) | all 6 jobs PASS |
| #103 | `2daaab4181e3` | 5 commits, 24 files | [45359903577](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45359903577) | all 6 jobs PASS |

## Review outcome

- **No merge conflicts:** `git merge-tree` reported no "changed in both" files; each PR extends the previous one rather than duplicating it.
- **No weakened tests:** every deletion in a test file was a refactor that preserved or strengthened assertions. Each new script has an owning test discovered by CI.
- **No duplicate implementations across PRs:** PR #103 hardens PR #100/#102 artifacts (e.g. adds fingerprint and signature checks) instead of replacing them.

## Confirmed defects found in the review (fixed on the final branch)

| Severity | Defect | Fix |
| --- | --- | --- |
| High | Docker in-container fingerprint excluded `sqlite_%` differently from host; real AUTOINCREMENT DBs would report a false mismatch | single shared `fingerprint_from_connection()` source embedded in the container snippet; AUTOINCREMENT fixture added |
| High | Failed off-host upload left a `prune` journal phase; a later resume finalized it as `completed` | failed upload no longer advances the journal; resume refuses an uncompleted upload; `retry-upload` finalizes the journal |
| High | Login lockout could be bypassed once all tracked keys were actively locked | bounded rejected-key set fails closed for new keys |
| Medium | Protocol-relative URLs (`//evil.example`) received the CSRF token | `apiClient.ts` rejects protocol-relative/cross-origin references |
| Medium | Recovery evidence paired newest backup, newest restore and newest restart independently; CLI always exited 0 | pairing check added; CLI returns non-zero for incomplete evidence |
| Medium | Migration rollback replaced the DB but left stale WAL/SHM sidecars | shared `remove_sidecars()` called after rollback |
| Medium | Restore overwrite had no rollback snapshot or failed report | pre-restore snapshot with checksum, atomic rollback and failed-report artifact |
| Medium | Backup parity compared row counts only; Docker snippet used a different clock/table filter | content digest + FK violations in fingerprints; shared algorithm |
| Medium | S3 adapter accepted invalid config, had no retry, discarded ETag/version and wrote downloads directly | adapter-side config validation, bounded transient retry, digest-checked atomic `.part` download, metadata capture |
| Low | `AgentNetwork` used `||` with a localhost fallback and displayed "550+" | `??` with relative API URL; corrected count |
| Low | `provider_health.report(now=...)` mixed injected and wall clocks | `now` forwarded to `health()` |
| Low | Cron fields/calendar unvalidated; IPv6 loopback rejected; host tooling not preflighted | per-field cron validation, IPv6 loopback accepted, host-tooling preflight check |

## Final follow-up audit (before delivery)

A second read-only audit of the final diff found and fixed six more confirmed defects, each with a regression test:

| Defect | Fix |
| --- | --- |
| Strict restore rejected a byte-identical backup that already contained an FK violation | `_compare` now requires equality of violation sets, not absence of violations |
| Pre-restore snapshot could lose WAL-committed data; failed reports could be skipped | snapshot uses `sqlite3.Connection.backup()` with byte-copy fallback; rollback removes sidecars and always writes a failed report |
| Recovery report could say `evidence_complete` while an interrupted journal existed | `journal_status == completed` is now required; CLI fails closed |
| Host preflight validated the shipped `install_schedule.py` rather than the audited `--root` copy | audited module is loaded from the target root via `importlib.util` |
| Normal no-upload backups lost journal fidelity (`upload.status`) | benign `not_configured`/`dry_run` outcomes are recorded again |
| `retry_upload` finalization, FK parity and interrupted-journal gating lacked tests | added dedicated regression tests |

## Not fixed / explicitly out of scope

- Real cloud S3 restore, real host service/Docker recovery and independent security sign-off remain **BLOCKED**; no mock is counted as external evidence.
- Cross-origin `VITE_API_URL` remains unsupported in dual-auth mode (documented); the built Compose stack uses a same-origin empty value.
- Supervisor lease expiry during a long dispatch remains a documented hypothesis pending a real multi-host reproduction.

No PR was merged; the final branch is a stacked PR on #103 for review.
