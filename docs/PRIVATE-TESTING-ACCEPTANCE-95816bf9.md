# Private-testing acceptance report — exact commit `9fdc0220`

Scope: controlled **private, local, research-only** testing. This report does
not authorize public production promotion, which remains on HOLD. Evidence was
collected on 2026-11-28 against HEAD `9fdc0220ae0013a70a86d2b90c1d80f39377555c`
(the evidence table in `PROMOTION-CHECKLIST.md` was added by this same commit and
documents the immediately preceding head `95816bf9`). `96816bf9` is not a valid
git object; it is treated as a typo for `95816bf9`.

## Verified acceptance criteria (private testing)

| Criterion | Command / evidence | Result |
| --- | --- | --- |
| Backend unit/integration | `PYTHONPATH=.:./backend .venvs/backend/bin/python -m unittest discover -s backend/tests -q` | **1546 OK, 1 skipped**, exit 0 |
| Frontend typecheck | `npm run typecheck` (terminal) | exit 0 |
| Frontend lint | `npm run lint` (terminal) | exit 0 |
| Production build | `npm run build` (terminal, clean `.next`) | exit 0 |
| Migration history check | `npx drizzle-kit check` | exit 0 |
| Dependency security | `npm audit --audit-level=moderate` | exit 0, 0 vulns |
| Demo-mode terminal | `node scripts/verify-terminal.mjs` | **46 PASS, exit 0** |
| Unreachable-database fallback | `node scripts/verify-unreachable-db.mjs` | **21 PASS, exit 0** |
| Docs integrity | `python3 scripts/check_doc_links.py` | 88 files resolve, exit 0 |
| CI on exact head | workflow runs `46146341020`, `46146336842` | all required jobs SUCCESS |

CI evidence:
- https://github.com/djny45/-MARKET-MIND-AI/actions/runs/46146341020
- https://github.com/djny45/-MARKET-MIND-AI/actions/runs/46146336842

## Six external gates — scope classification

| Gate | Classification | Reason |
| --- | --- | --- |
| G1 TLS issuance/scan | **Deferred production requirement** | Requires public host and CA; private loopback research needs no public TLS |
| G2 Network segmentation | **Deferred production requirement** | Requires host firewall/ACL evidence; local services bind loopback |
| G3 Ingress hardening | **Deferred production requirement** | Requires deployed public ingress; none exists in private scope |
| G4 Independent security sign-off | **Deferred production requirement** | Formal go/no-go for public exposure; owner waiver covers private use only |
| G5 Licensed market-data/legal review | **Deferred production requirement** | Only relevant to redistribution/public feed; private research uses attested public bars under owner acceptance |
| G6 Host recovery drill | **Deferred production requirement** | Requires root/systemd/Docker host; non-privileged drill evidence exists only locally |

None of the six gates is **required for private research-platform testing**; all
six are **excluded from the agreed private-testing scope** by
`docs/PRIVATE-OPERATIONAL-LAUNCH-REPORT.md` and `docs/FINAL_RELEASE_AUDIT.md`.
`ingress-gate-evidence.json` records 0/6 passed and `public_ingress_enabled:
false` — that is the correct private posture, not a failure of this scope.

## Known limitations (private testing)

- No browser binary, camofox REST service or authenticated Vercel MCP is
  available in this environment; viewport/console/network inspection of a
  deployed preview was not performed and is not claimed.
- Vercel's terminal project remains rate-limited; no exact-head READY preview
  exists. `verify-deployed.mjs` was therefore not run against any deployment.
- No independent `APPROVED` GitHub review exists; the owner's documented
  waiver applies to private local use only.
- `DATABASE_URL` remains unset by ADR-006. The optional
  `MARKET_MIND_RESEARCH_DB` bridge reads operator-attested `binance-public`
  15m bars read-only and labels them as research data, never live/execution-grade.
- Full PostgreSQL migration of all application stores is out of scope; see
  `POSTGRES-MIGRATION-GAP.md`.

## Decision

**TEST READY for private, local, research-only use** — every agreed private
acceptance criterion above is independently verified on the exact commit.
**PRODUCTION PROMOTION: HOLD** — all six external gates, independent approval,
exact-head preview inspection and `verify-deployed.mjs` exit 0 remain separate
requirements that have not been met. No merge, deployment or production setting
change was made.
