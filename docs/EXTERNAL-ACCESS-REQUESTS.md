# External access and sign-off requests (prepared, not submitted)

Status: **requests drafted**. No endpoint, credential, host or reviewer has been
invented, and no external person has been contacted by this work. These are
ready-to-send texts for the responsible parties; the repository owner must
submit them through an approved channel and record the response.

---

## EXT-01 — Request for authorized S3 restore access (ACC-029)

**To:** cloud infrastructure owner (IAM authority) *and* owner of the private
database host.
**Need:** a scoped, disposable S3-compatible bucket and a host to run the
read-only restore drill. No production database may be used.

**Exact missing values (must be supplied by the owner, never guessed):**

| Item | Value in this repository | Required from owner |
| --- | --- | --- |
| Endpoint | none | e.g. `https://s3.<region>.amazonaws.com` or `https://minio.internal:9000` |
| Bucket | none | dedicated test bucket name |
| Region | none | provider region string |
| Access key ID | none | scoped credential, delivered out of band |
| Secret access key | none | delivered out of band, stored in a 0600 EnvironmentFile |
| Object prefix | `market-mind/backups` (default) | confirm or override with `MARKET_MIND_S3_PREFIX` |
| Host | none | authorized private host with Python 3.11+ and an isolated restore directory |

**Permissions to grant (least privilege, prefix-scoped where supported):**

- `s3:PutObject`, `s3:GetObject` on `<bucket>/market-mind/backups/*`.
- `s3:ListBucket` on `<bucket>` (only if the operator needs to enumerate keys).
- Explicitly **not** granted: bucket creation/deletion, `s3:DeleteObject`,
  `s3:PutBucketPolicy`, wildcard resource ARNs, production-bucket access.
- Bucket-side settings owned by the operator: versioning, object lock,
  server-side encryption at rest, public-access block, TLS-only policy.
- Credentials must be revocable and rotated after the drill.

**Verification without exposing secrets:**

```bash
python3 scripts/config_preflight.py --root .
python3 scripts/s3_offhost.py validate-config
python3 scripts/s3_offhost.py describe-config --dry-run   # prints names only
```

The adapter uses AWS SigV4 path-style PUT/GET only; it cannot create or
configure buckets, use session tokens, SSE-C/KMS headers or multipart upload.
The operator must confirm provider compatibility before the drill.

**Deliverable expected back:** a completed `docs/external-evidence/EXT-01.json`
bundle with the redacted artifacts listed in its template, plus operator
identity and timestamp. Procedure and rollback:
`docs/EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-01.

**Ready-to-send text:**

> Please provide a disposable prefix-scoped S3-compatible bucket and credentials
> for the MARKET-MIND-AI backup/restore validation, plus an authorized private
> host. Required actions are s3:PutObject, s3:GetObject on the backup prefix and
> s3:ListBucket on the bucket; versioning, object lock, encryption and
> public-access block are bucket-side settings. No production data or real
> financial transactions are involved. Please deliver credentials out of band
> for a 0600 EnvironmentFile and confirm the endpoint, bucket, region and
> operator identity so we can run the documented restore procedure and capture
> the evidence bundle. Credentials will be rotated after the drill.

---

## EXT-02 — Request for authorized host service drill (ACC-030)

**To:** host/system administrator with root and the service owner.
**Need:** a disposable Linux host (or maintenance window) with systemd or
crontab, Docker engine if the volume sub-drill is included, and an authorized
operator to execute the controlled restart.

**Permissions required:**

- sudo/root for `systemctl daemon-reload`, `systemctl enable --now`,
  `systemctl list-timers`, `systemctl status`, `journalctl`, and removal of
  generated units after the drill.
- ability to create `/etc/market-mind/market-mind.env` with mode 0600 holding
  `MARKET_MIND_DB`, `MARKET_MIND_DR_STATE_DIR`, retention and webhook settings.
- crontab write access only if the cron variant is used.
- Docker daemon access only for the named-volume sub-drill; source volume must
  never be deleted.
- production restart requires an explicit maintenance window and a separately
  verified pre-drill backup.

**What is already safe locally:** `scripts/install_schedule.py plan` writes
nothing and invokes no `systemctl`/`crontab`; `scripts/host_recovery_plan.py`
only aggregates read-only plans; `scripts/config_preflight.py` runs offline.

**Environment limitation confirmed here (2026-11-24):** no `docker`, no
`systemctl`, no `crontab`, non-root uid 1000. Container/process tests are not
host-level validation and are not claimed as such.

**Deliverable expected back:** completed `docs/external-evidence/EXT-02.json`
with `systemctl status`/`list-timers`, redacted journal excerpt, restart and
recovery reports, volume-drill result, host identity and operator name.
Procedure and rollback:
`docs/EXTERNAL-VERIFICATION-CHECKLIST.md` § EXT-02.

**Ready-to-send text:**

> Please schedule a controlled MARKET-MIND-AI service restart and recovery drill
> on an authorized host. We need root access for systemd/timer installation and
> a 0600 EnvironmentFile, plus a short stale-lock threshold during the drill.
> The read-only plan generator is already in the repository; no production
> writes or real market trades occur. Please capture systemctl status/list-timers,
> redacted journal output, the restart/recovery JSON reports and (if in scope)
> the Docker named-volume backup/restore result, then complete the EXT-02
> evidence bundle. We will disable generated units and remove only the
> disposable target volume afterwards.

---

## EXT-03 — Request for independent security review and sign-off (ACC-031)

**To:** independent security lead or penetration-test provider, and the
repository owner who accepts or rejects the decision.
**Need:** a reviewer with no production write credentials, a staging deployment
behind the reviewed TLS ingress, test identities for each role, and written
rules of engagement and scope.

**Reviewer/signer identification (must be filled by the owner):**

- Review firm / independent reviewer name: **not identified here**.
- Signer of the go/no-go decision: **not identified here** (repository owner).
- Review date, report ID and decision date: **not yet available**.

**Package supplied:** `docs/SECURITY-REVIEW-PACKAGE.md` (architecture,
authentication, authorization, permissions, secrets management, threat model,
dependency inventory, CI scan results, pen-test scope and evidence checklist),
`docs/PUBLIC-EXPOSURE-HARDENING.md`, `SECURITY_AUDIT.md`, and the read-only MCP
allowlist described in `AGENTS.md`.

**Local scans recorded (internal evidence, not independent approval):**
`pip-audit -r backend/requirements.txt` and `npm audit --audit-level=high
--omit=dev` both report no known vulnerabilities; Trivy filesystem and container
scans report 0 findings on PR #107 head. These will be re-run for the reviewer
and supplied as scanner output, but they do not substitute for an independent
review or a signed report.

**Deliverable expected back:** completed `docs/external-evidence/EXT-03.json`
with rules of engagement, scope, findings and remediation/retest dates, scanner
and TLS outputs, and a signed go/no-go statement. Until then public ingress stays
disabled and the platform remains in private research-only mode.

**Ready-to-send text:**

> Please perform an independent security review and authorized penetration test
> of MARKET-MIND-AI staging under written rules of engagement. The review
> package, threat model, architecture, auth/authz boundaries, secrets policy and
> current dependency/container scan results are in the repository. Please
> exercise auth/session/CSRF, role and ownership boundaries, rate limiting,
> TLS/ingress configuration and network segmentation, record each finding with
> severity and retest date, and issue a signed go/no-go decision. We will not
> self-certify the outcome or enable public ingress without your sign-off.

---

## Submission status

| Check | Request drafted | External party identified | Submitted | Response |
| --- | --- | --- | --- | --- |
| EXT-01 | yes | no (owner must name IAM/host owner) | no | none |
| EXT-02 | yes | no (owner must name host admin) | no | none |
| EXT-03 | yes | no (owner must name reviewer/signer) | no | none |
