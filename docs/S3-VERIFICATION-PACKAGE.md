# ACC-029 — S3 verification package (preparation only)

Status: **BLOCKED**. This document prepares an authorized external drill; it
does not claim that a bucket, credentials, encryption settings or a real restore
exist in this repository. All local adapter tests are mock-based contract tests.

## 1. Supported S3-compatible providers

`scripts/s3_offhost.py` uses stdlib `http.client` with AWS SigV4 **path-style**
requests (`PUT/GET /<bucket>/<key>`), `x-amz-content-sha256`, `x-amz-date` and an
`Authorization` header. Providers that expose this contract should work; each
must be confirmed by the external operator.

| Provider | Endpoint example | Notes to confirm |
| --- | --- | --- |
| AWS S3 | `https://s3.<region>.amazonaws.com` | Path style is supported for existing buckets; IAM scoped to prefix. |
| MinIO | `https://minio.internal:9000` | Self-managed TLS, bucket versioning/object lock, regional name arbitrary. |
| Cloudflare R2 | `https://<account>.r2.cloudflarestorage.com` | S3 API compatibility and token permissions must be verified. |
| Backblaze B2 (S3 API) | `https://s3.<region>.backblazeb2.com` | Verify SigV4 path style and key policy. |
| Wasabi | `https://s3.<region>.wasabisys.com` | Verify region string and path-style addressing. |
| Ceph RGW / Garage | operator endpoint | Verify SigV4 implementation and bucket features. |

Not supported by the adapter itself: multipart upload, query-string signing,
SSE-C/SSE-KMS request headers, object tagging/Lifecycle APIs, retries/backoff,
bucket creation, deletion/listing, or streaming (the whole file is read into
memory). Those are provider/operator responsibilities or future work, not
claimed capabilities.

## 2. Configuration contract and preflight diagnostics

Required environment (values only in a 0600 EnvironmentFile, never in Git):
`MARKET_MIND_S3_ENDPOINT`, `MARKET_MIND_S3_BUCKET`, `MARKET_MIND_S3_REGION`,
`MARKET_MIND_S3_ACCESS_KEY`, `MARKET_MIND_S3_SECRET_KEY`.
Optional: `MARKET_MIND_S3_PREFIX` (default `market-mind/backups`).

Safe local diagnostics (no network, no values printed):

```bash
python3 scripts/config_preflight.py --root .      # dr_environment + TLS/ingress/Compose gates
python3 -c "import sys; sys.path.insert(0,'scripts'); import dr_common, json; print(json.dumps(dr_common.validate_dr_environment()))"
# with the five MARKET_MIND_S3_* variables exported by the operator:
python3 scripts/s3_offhost.py describe-config --dry-run
```

`validate_dr_environment()` fails closed on partial S3 configuration, non-HTTPS
endpoints outside loopback, invalid bucket/region names and `..` in the prefix.
It reports variable names, never values. `describe-config --dry-run` confirms
presence and `credentials_exposed=false` without contacting the endpoint.

## 3. Encryption, checksums, metadata and restore integrity

- **In transit:** the adapter selects `HTTPSConnection` for `https://` endpoints.
  Operators must verify certificate validity and TLS version at the endpoint.
- **At rest:** bucket default encryption (SSE-S3/SSE-KMS or provider equivalent),
  versioning, object lock and public-access blocking are **operator-side bucket
  settings**; the adapter does not set or verify them. Capture the bucket policy
  and encryption configuration as evidence.
- **Integrity:** SigV4 signs `x-amz-content-sha256` for every PUT and GET; the
  fake-S3 test verifies signature correctness. Separately,
  `backup_orchestrator.py` writes a `.sha256` sidecar and a `.json` manifest with
  `database_fingerprint` (integrity check, per-table row counts, schema version,
  bytes). `restore_orchestrator.py` verifies the checksum/manifest before copying
  and compares the fingerprint after restore.
- **Object metadata:** use the configured prefix plus the backup filename as the
  object key (`{prefix}/{name}`). The adapter sends no custom metadata headers;
  record bucket/region/prefix/key, object size, ETag/version ID (if available)
  and server-side encryption setting in the external evidence bundle.
- **Restore integrity:** only `restore_orchestrator.py verify|restore` plus
  `database_fingerprint` parity may establish restore integrity. A successful
  PUT/GET alone is not a restore.

## 4. Exact real-cloud procedure

The authoritative numbered procedure is in
`docs/EXTERNAL-VERIFICATION-CHECKLIST.md` → EXT-01. It covers describe-config,
backup with the upload hook, explicit `retry-upload --backup`, download, SHA-256
parity, clean-directory restore, isolated restart-recovery evidence and
`recovery_report.py --root <dir> --state-dir <state>` with
`status=evidence_complete`.

Expected evidence: redacted transcripts, sidecar/manifest, bucket encryption and
versioning settings, object key/version/ETag, restore report with `comparison=matched`,
restart report, aggregated report, operator identity and timestamp.

## 4a. Required infrastructure, permissions and accountability

- **Infrastructure:** authorized S3-compatible endpoint, dedicated bucket with
  versioning, object lock and server-side encryption enabled, private network
  path, and an isolated host with Python 3.11+ and this checkout.
- **Permissions:** scoped IAM/token allowing `PutObject`, `GetObject` and
  `ListBucket` only on the configured prefix; no production write credentials;
  credentials supplied via a 0600 EnvironmentFile, never in Git or command lines.
- **Expected result:** all commands exit 0; local/downloaded SHA-256 and the
  backup fingerprint match; restore comparison `matched`; integrity `ok`; no
  secret value in any output or artifact.
- **Evidence to capture:** redacted transcripts, bucket encryption/versioning
  policy, object key/version/ETag, sidecar and manifest, restore report,
  restart report, `recovery_report.py` JSON, operator identity and timestamp.
- **Rollback:** never overwrite the live database; discard the isolated copy.
  If a service DB was touched, stop writes and restore the separately verified
  pre-drill backup; revoke/rotate credentials used for the drill.
- **Responsible external operator:** cloud infrastructure owner (IAM) plus the
  host operator who owns the private database. Both must sign the evidence.

## 5. Honest boundary

No real cloud target was contacted. Passing local fake-S3 tests proves only the
CLI/signature/parity contract. ACC-029 stays BLOCKED until an authorized
operator performs EXT-01 and supplies the evidence above. See
`docs/EXTERNAL-VERIFICATION-CHECKLIST.md` for rollback and responsible operators.
