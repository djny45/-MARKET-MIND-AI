# FINAL TEST RESULTS — executed 2026-11-22

All results below were produced by commands run in this workspace. Nothing is
inferred from documentation.

| # | Check | Command / source | Result |
| --- | --- | --- | --- |
| 1 | Backend unit + integration tests | `PYTHONPATH=.:./backend python -m unittest discover -s backend/tests -q` | **923 tests, OK** (includes 14 per-user auth tests) |
| 2 | Frontend unit tests | `cd frontend && npm test` (`node:test`) | **5 tests, 5 pass, 0 fail** |
| 3 | Frontend production build | `cd frontend && npm run build` | success |
| 4 | Frontend project-site build | `VITE_BASE_PATH=/MARKET-MIND-AI/ npm run build` | success; asset/page URLs rewritten |
| 5 | Dependency audit | `npm audit --omit=dev --audit-level=high` | 0 vulnerabilities |
| 6 | Skill/worker integrity | `full_integrity_report()` | 325 + 89 = 414 skills, 550 workers, 0 issues |
| 7 | Read-only browser tool (live) | MCP `browser_research_read` → `https://en.wikipedia.org/wiki/Market` | HTTP 200, 4,528 chars, side effects false |
| 8 | Full browser (live) | Camofox MCP `camofox_create_tab` + `camofox_snapshot` → `https://example.com` | HTTP 200, snapshot content returned; `browserConnected: true` |
| 9 | GitHub Actions quality workflow | `gh run list` on `main` | success (run `45004631077`, merge of PR #61; final documentation commit will trigger a new run) |
| 10 | Docker Compose config | `docker compose config` | **not run locally** — `docker` binary absent; CI authoritative |
| 11 | Trivy filesystem scan | `trivy` | **not run locally** — binary absent; CI authoritative |
| 12 | Python dependency audit | `pip-audit` | **not run locally** — tool unavailable |

## Test categories covered by the 909 backend tests

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
