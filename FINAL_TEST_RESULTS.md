# FINAL TEST RESULTS — executed 2026-11-22

All results below were produced by commands run in this workspace. Nothing is
inferred from documentation.

| # | Check | Command / source | Result |
| --- | --- | --- | --- |
| 1 | Backend unit + integration tests | `PYTHONPATH=.:./backend python -m unittest discover -s backend/tests -q` | **987 tests, OK** (includes per-user auth, research-loop, and market-utility suites) |
| 1b | Skill/worker/system integrity | `full_integrity_report()` | 325 catalog + 89 reference = 414 definitions, 550 workers, 0 issues |
| 2 | Frontend unit tests | `cd frontend && npm test` (`node:test`) | **10 tests, 10 pass, 0 fail** |
| 3 | Frontend production build | `cd frontend && npm run build` | success |
| 4 | Frontend project-site build | `VITE_BASE_PATH=/MARKET-MIND-AI/ npm run build` | success; asset/page URLs rewritten |
| 5 | Dependency audit | `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| 6 | Skill/worker integrity | `full_integrity_report()` | 325 + 89 = 414 skills, 550 workers, 0 issues |
| 7 | Read-only browser tool (live) | MCP `browser_research_read` → `https://en.wikipedia.org/wiki/Market` | HTTP 200, 4,528 chars, side effects false |
| 8 | Full browser (live) | Camofox MCP `camofox_create_tab` + `camofox_snapshot` → `https://example.com` | HTTP 200, snapshot content returned; `browserConnected: true` |
| 9 | GitHub Actions quality workflow | `gh run list --branch main` | success (run `45015450017`, merge of PR #28, 2m34s; PR #26 rerun success) |
| 10 | Backup/restore drill (host) | `python3 backend/backup_database.py` → `python3 backend/restore_database.py` | Verified 2026-11-22: backup + restore of `data/market_mind.db` — both `verified`/`restored_and_verified`, `integrity_check=ok`, row-count parity across all tables |
| 11 | Trivy CI (local) | `trivy fs --scanners misconfig,secret --severity MEDIUM,HIGH,CRITICAL .` | blocked from pushing by OAuth `workflow` scope; file committed locally (`feat/trivy-fs`, `1827be8`) |
| 12 | Docker Compose config | `docker compose config` | **not run locally** — `docker` binary absent; CI authoritative |
| 13 | Trivy filesystem scan | `trivy` | **not run locally** — binary absent; CI authoritative (blocked by OAuth scope; see below) |
| 12 | Python dependency audit | `pip-audit` | **not run locally** — tool unavailable |

## Test categories covered by the 987 backend tests

API contract and route behaviour, agent registry (550 profiles), worker routing,
skill catalog (325), persistent memory, research pipeline, historical evaluation,
supervisor/task lifecycle (recovery, cancellation, retry), API auth middleware,
rate limiting, environment validation, backup/restore helpers, and the imported
browser-research policy.

## Notes

- No skipped or xfail tests were found in the backend suite.
- Frontend tests are limited to build-path utilities; there is no React DOM test
  runner in the repository.
- Local execution of Docker/Trivy is impossible in this container; their status
  is reported honestly rather than claimed as passing.
