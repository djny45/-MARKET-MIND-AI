# External evidence bundles (intake only)

Status: **prepared, nothing completed**. This document defines how an authorized
operator records EXT-01/02/03 evidence. It does not execute any external check
and does not grant approval.

The three acceptance rows stay `blocked` until an external operator supplies a
complete bundle and the repository owner records that bundle's evidence path.
Local mock/fake/moto/simulated runs, container-only tests and this repository's
own security audit **cannot** close these rows.

## Intake contract

`scripts/external_evidence.py` is the fail-closed gate:

```bash
# Prepare a fresh pending template (the checked-in files are pending templates):
python3 scripts/external_evidence.py template --id EXT-01 --output /secure/EXT-01.json

# Validate a bundle supplied by the external operator:
python3 scripts/external_evidence.py validate --bundle /secure/EXT-01.json

# Report acceptance counts; never mutates the inventory:
python3 scripts/external_evidence.py audit
```

`validate` exits 0 only when **all** of the following hold:

1. `outcome` is `passed` and every required field is non-empty.
2. `operator_identity`, `owner_identity`, `executed_at` and `environment` are
   supplied by the external operator.
3. Every required artifact in `docs/external-evidence/<check>.json` exists and
   its SHA-256 matches the recorded digest.
4. Every required boolean check is `true`.
5. `environment` contains no mock/fake/moto/simulated/stub/dry-run marker.
6. No secret-looking value (AWS key ID, private key header, GitHub token, S3
   secret assignment or bearer JWT) appears in the bundle.
7. The bundle does not claim `external_approval: approved` — a bundle cannot
   self-certify independent sign-off.

A passing result means *structurally complete evidence*, **not** approval. The
go/no-go decision remains with the external operator named in
[`EXTERNAL-ACCESS-REQUESTS.md`](EXTERNAL-ACCESS-REQUESTS.md).

## Bundle locations

| Check | Acceptance row | Pending template | Procedure |
| --- | --- | --- | --- |
| EXT-01 | ACC-029 | `docs/external-evidence/EXT-01.json` | `docs/S3-VERIFICATION-PACKAGE.md`, `docs/EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-01 |
| EXT-02 | ACC-030 | `docs/external-evidence/EXT-02.json` | `docs/HOST-RECOVERY-PROCEDURE.md`, `docs/EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-02 |
| EXT-03 | ACC-031 | `docs/external-evidence/EXT-03.json` | `docs/SECURITY-REVIEW-PACKAGE.md`, `docs/EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-03 |

Store real artifacts and credentials outside Git. Only the bundle JSON and
redacted artifacts belong in the repository; never commit a private key, access
key, session token or full journal containing secrets.

## Recording a closure

Only after `validate` succeeds and the external operator signs the outcome:

1. Place the redacted bundle and artifacts in an operator-owned evidence path.
2. Record the exact path, bundle ID, operator identity and decision date in
   `docs/acceptance-inventory.json`, changing that single row from `blocked` to
   `verified` and setting `evidence_status` to `verified_external`.
3. Re-run `python3 scripts/external_evidence.py audit` and confirm the new count.
4. Update `docs/FINAL_RELEASE_AUDIT.md` with the new evidence reference.

Do not edit a status without a matching validated bundle. Do not weaken the
validator to make a bundle pass.
