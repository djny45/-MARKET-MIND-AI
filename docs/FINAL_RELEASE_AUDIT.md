# Final release audit — 2026-11-24

Scope: verify the delivered repository state, separate verified local evidence
from external evidence, and state the release boundary. No external credential,
host or independent approval was used or invented. Nothing below claims a
completed EXT-01/02/03 drill.

## 1. Git and PR status

| Item | Verified value |
| --- | --- |
| Verified baseline HEAD | `feature/alpine-backend-runtime` @ `d535277e8d433f729d6ab87a1e5ee03f047e38a9` (clean tree before this audit's documentation/tooling changes) |
| `origin/main` | `1a13bfe28974ebdf2877ba0180889122aeafd7e0` (2026-11-23T21:19:43Z) — no commits absent from the PR stack |
| PR #107 | OPEN, `MERGEABLE`, `CLEAN`; base `feature/phase5-risk-resolution`; head matches local HEAD |
| PR #107 CI | run `45462154531` — all 7 required jobs SUCCESS: Backend, Frontend, Docker Compose integration, Dependency audit, Trivy filesystem, Container image scan, Real browser responsive tests. cubic review NEUTRAL; two Vercel preview statuses SUCCESS |
| Merge stack | #100 → #102 → #103 → #104 → #105 → #106 → #107, all MERGEABLE. #100/#102/#103/#104/#107 `CLEAN`; #105/#106 `UNSTABLE` (their older heads carry stale checks) — merge in order and re-check each head |
| Production deployments | `gh api .../deployments` returned no production deployment. Vercel preview statuses are PR previews, not a production release |

## 2. Regression and CI results re-run for this audit

Executed locally on the HEAD above (this environment):

| Check | Command | Result |
| --- | --- | --- |
| Backend | `PYTHONPATH=.:./backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q` | **1269 OK, 1 skipped** (159.6 s) — 1261 baseline + 8 new intake tests |
| Backend evidence intake | `python -m unittest backend.tests.test_external_evidence` | **8 OK** |
| Frontend unit (Node 22.23.5) | `npm test` | **10/10 pass** |
| Frontend UI (Node 22.23.5) | `npm run test:ui` | **21 files, 127/127 pass** |
| Python dependency audit | `pip-audit -r backend/requirements.txt` | **No known vulnerabilities found** |
| npm production audit | `npm audit --audit-level=high --omit=dev` | **found 0 vulnerabilities** |
| Doc links | `python3 scripts/check_doc_links.py` | **all relative links resolve (64 files)** |
| External intake audit | `python3 scripts/external_evidence.py audit` | **40 items: 37 verified, 3 blocked; 92.5%** |
| Browser E2E | CI job "Real browser responsive tests" | **9/9 pass** (run `45462154531`); local run requires Node 22 + the recorded library prefix |
| Container scan | CI "Container image security scan" on head `8785e468` / run `45420717539` and PR #107 | **0 findings** (Trivy MEDIUM+, `ignore-unfixed=false`, no ignore file) |

Note: Node 20 cannot run the installed Vitest (`crypto.hash` needs Node 22+);
the UI result above was obtained with Node 22.23.5 from the local nvm prefix.

## 3. Security findings

- No Critical/High findings in the executed dependency or container scans.
- `docs/CONTAINER-SCAN-FINDINGS.md` records 137 → 0 remediation by replacing the
  Debian 13 runtime with pinned `python:3.12.16-alpine3.24` and removing the
  base system pip; no suppressions or threshold changes.
- `SECURITY_AUDIT.md`, `docs/SECURITY_IMPLEMENTATION.md` and
  `docs/SECURITY-REVIEW-PACKAGE.md` are **internal** documentation. They do not
  constitute the independent review required by ACC-031.
- The read-only MCP allowlist and research-only/no-trading boundary in
  `AGENTS.md` remain in force. No real financial transaction was executed.

## 4. External gates (not closable here)

| Check | Row | State | Evidence actually available |
| --- | --- | --- | --- |
| EXT-01 cloud S3 restore | ACC-029 | **BLOCKED** | preparation package and pending intake template; no endpoint, bucket or credentials exist here |
| EXT-02 host service drill | ACC-030 | **BLOCKED** | read-only plans and contract tests; this environment has no docker, systemctl, crontab or root |
| EXT-03 independent review | ACC-031 | **BLOCKED** | review package and internal scans; no independent reviewer or signed decision |

Intake is fail-closed: `scripts/external_evidence.py validate` rejects pending,
mock/simulated, tampered, secret-bearing or self-certifying bundles. Acceptance
rows were **not** changed to verified. Exact requests and required permissions
are in `docs/EXTERNAL-ACCESS-REQUESTS.md`; intake rules are in
`docs/EXTERNAL-EVIDENCE-BUNDLES.md`.

## 5. Production deployment status

Local and CI verification is not production validation. No production deployment
is recorded in the GitHub deployments API; only PR preview deployments appear in
the PR status rollup. Public deployment gates remain **0/6** (TLS issuance/scan,
network segmentation, ingress hardening, independent security sign-off, licensed
market-data provider/legal review, host recovery drill). Public ingress must stay
disabled. The platform is release-ready **only** for private, research-only
self-hosting under the documented constraints.

## 6. Completion

- Acceptance inventory: **37/40 verified (92.5%)**, 0 partial, 3 BLOCKED.
- Private research-platform gates: **7/10 (70%)**.
- Public deployment readiness: **0/6 (0%)**.
- Locally achievable engineering work for this final cycle: **complete**.
- Overall release readiness: **not complete** until EXT-01/02/03 evidence and
  independent sign-off are supplied by authorized external parties.

The percentage is not a release authorization: the remaining 7.5% of acceptance
items are external by definition and cannot be closed by more local testing.
