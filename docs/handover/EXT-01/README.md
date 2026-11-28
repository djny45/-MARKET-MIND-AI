# Handover package EXT-01 — real cloud S3 restore (ACC-029)

Status: **BLOCKED — evidence not supplied**. Nothing in this package was run
against a real cloud account. Prepared by the repository; execution and sign-off
belong to the cloud infrastructure owner and the private database host owner.

## Package contents

| File | Purpose |
| --- | --- |
| `../../S3-VERIFICATION-PACKAGE.md` | Provider compatibility, config contract, encryption/checksum/metadata requirements, restore integrity rules |
| `../../EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-01 | Exact 7-step drill, expected result, evidence list, rollback |
| `../../EXTERNAL-ACCESS-REQUESTS.md` § EXT-01 | Ready-to-send access request and least-privilege permissions |
| `../../external-evidence/EXT-01.json` | Pending intake template (no evidence yet) |
| `../../../scripts/s3_offhost.py`, `backup_orchestrator.py`, `restore_orchestrator.py` | Operator commands; contract tests only |
| `../../../scripts/external_evidence.py` | Fail-closed bundle validator |

## What the external operator must supply

- S3-compatible endpoint, dedicated bucket, region, prefix, scoped credentials
  (`PutObject`/`GetObject` on the prefix, `ListBucket` on the bucket) in a 0600
  EnvironmentFile; versioning, object lock, encryption at rest and public-access
  block configured bucket-side. No wildcard IAM, no production bucket access.
- An authorized private host with Python 3.11+ and an isolated restore path.
- Redacted command transcripts: describe-config, backup manifest, upload/download
  results, SHA-256 parity, restore report, restart/recovery report, recovery JSON,
  bucket/key/version ID (never credentials), operator identity and timestamp.

## Entry / success / abort criteria

- Entry: `python3 scripts/s3_offhost.py validate-config` and
  `describe-config --dry-run` report `credentials_exposed=false`.
- Success: all commands exit 0; SHA-256 parity; `restore_comparison_matched`;
  `integrity=ok`; no secrets in any output; isolated target only.
- Abort: never overwrite the live database; discard the isolated copy; if a
  service DB was touched, stop writes and restore the verified pre-drill backup;
  rotate drill credentials. Never `docker compose down -v`.

## Closure

Operator completes the bundle, then:
`python3 scripts/external_evidence.py validate --bundle <bundle>` must pass.
Only then may the owner change ACC-029 to `verified` with the bundle path and
operator identity. A passing validator is evidence completeness, not approval.
