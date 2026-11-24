# Handover package EXT-03 — independent security review (ACC-031)

Status: **BLOCKED — no independent reviewer, signed report or go/no-go decision
exists**. Internal audits and CI scans are not independent approval.

## Package contents

| File | Purpose |
| --- | --- |
| `../../SECURITY-REVIEW-PACKAGE.md` | Threat model, architecture, auth/authz, permissions, secrets management, dependency inventory, pen-test scope and evidence checklist |
| `../../EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-03 | Exact 5-step review/pen-test procedure, expected result, evidence list |
| `../../EXTERNAL-ACCESS-REQUESTS.md` § EXT-03 | Ready-to-send reviewer request; reviewer/signer still unnamed |
| `../../external-evidence/EXT-03.json` | Pending intake template (no evidence yet) |
| `../../../SECURITY_AUDIT.md`, `docs/SECURITY_IMPLEMENTATION.md`, `docs/PUBLIC-EXPOSURE-HARDENING.md` | Internal control evidence for reviewer orientation only |
| `../../../scripts/external_evidence.py` | Fail-closed bundle validator |

## Required from the independent party

- Written rules of engagement and scope; staging deployment behind the reviewed
  TLS ingress; test identities for viewer/analyst/operator/admin.
- Review of bearer/dual auth, CSRF and Origin enforcement, role hierarchy,
  ownership and unknown-resource denial; login throttling and audit events;
  TLS protocols/ciphers/HSTS, proxy hop count, ingress limits and segmentation.
- Authorized authenticated and unauthenticated penetration tests; finding IDs
  with severity, reproduction, remediation and retest dates.
- Signed go/no-go statement from the independent lead and acceptance by the
  repository owner. Neither role is self-certified by this repository.

## Entry / success / abort criteria

- Entry: reviewer has no production write credentials; scope and rules signed.
- Success: no open Critical/High findings; Medium findings have documented
  acceptance; 100% of planned scope executed; signed go/no-go decision.
- Abort: any open Critical/High keeps public ingress disabled and the service in
  private research-only mode; remediate, retest and re-review.

## Closure

Operator completes the bundle with rules of engagement, scope, findings, scanner
and TLS outputs, signed report and sign-off statement. Then
`python3 scripts/external_evidence.py validate --bundle <bundle>` must pass
before ACC-031 may be changed to `verified`. Public deployment gates (6) remain
0/6 until this and the other external gates pass.
