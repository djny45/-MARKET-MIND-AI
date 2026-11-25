# Acceptance closure evidence requirements — 9 open checks

This maps every open production-readiness check to its blocker, its exact
external dependency and the evidence required to close it. Nothing here is
marked complete without genuine evidence.

## 1. Mapping of the 9 open checks

| Open check | Blocker / gate | Locally resolvable work | External dependency |
| --- | --- | --- | --- |
| ACC-029 | EXT-01 real cloud S3 restore | Provider-independent config, AES-256-GCM encryption, adapter tests, local encrypted restore drill — all done | Authorized S3 endpoint, bucket, region, scoped keys, isolated host |
| ACC-030 | EXT-02 host restart/recovery | Non-privileged full-stack drill, bootstrap, host units, unprivileged login hook — all done | Root/systemd/Docker host, 0600 `/etc/market-mind/market-mind.env`, maintenance window |
| ACC-031 | EXT-03 independent review | Internal audit, threat model, scope and evidence package — all done | Independent reviewer, signed rules, findings, signed go/no-go |
| G1 TLS issuance/scan | Public ingress gate | TLS template, config preflight — done | Real certificate issuance and TLS scan on reviewed host |
| G2 network segmentation | Public ingress gate | Loopback-only perimeter, backend not host-published — done | Host/segmentation deployment evidence |
| G3 ingress hardening | Public ingress gate | nginx limits, CSP, headers, proxy config — done | Deployed public ingress hardening verification |
| G4 independent security sign-off | Public ingress gate | Same internal package as ACC-031 | Same as ACC-031 |
| G5 licensed data/legal review | Public ingress gate | Inventory, provenance checklist, gate tests — done | Named licensed provider, contract, written legal approval |
| G6 host recovery drill | Public ingress gate | Same local recovery drill as ACC-030 | Same as ACC-030, at production scale |

The three EXT blockers and the six gates total 9 open criteria. ACC-031 and G4,
and ACC-030 and G6, share the same underlying external evidence but are counted
separately because they are separate acceptance scopes.

## 2. EXT-01 / ACC-029 — exact closure evidence

Procedure: `docs/S3-VERIFICATION-PACKAGE.md`; handover:
`docs/handover/EXT-01/README.md`.

Required artifacts in `docs/external-evidence/EXT-01.json`, each with its real
SHA-256:

`describe-config.json`, `backup-manifest.json`, `upload-result.json`,
`download-result.json`, `restore-report.json`, `recovery-report.json`,
`sha256-parity.txt`.

Required checks, all `true`:

`sha256_parity`, `restore_comparison_matched`, `database_integrity_ok`,
`no_secrets_in_output`, `isolated_target_only`.

Required fields: non-empty `bundle_id`, `outcome=passed`, real `environment`,
`operator_identity`, `owner_identity`, `executed_at`, `procedure`, `notes`.

Closure command:

```
python3 scripts/external_evidence.py validate --bundle docs/external-evidence/EXT-01.json
```

The validator rejects mock/fake/simulated/dry-run/sandbox markers, secret-looking
values, self-certified approval and any false check. Current bundle: `pending`,
`closure_allowed=false`.

## 3. EXT-02 / ACC-030 / G6 — exact closure evidence

Procedure: `docs/HOST-RECOVERY-PROCEDURE.md`; handover:
`docs/handover/EXT-02/README.md`.

Required artifacts: `host-identity.txt`, `systemctl-status.txt`,
`list-timers.txt`, `restart-report.json`, `recovery-report.json`,
`journal-excerpt.txt`, `volume-drill-result.json`.

Required checks, all `true`: `timer_active`, `backup_freshness_ok`,
`stale_locks_removed`, `task_requeued_once`, `database_integrity_ok`,
`volume_comparison_matched`, `disposable_volume_removed`.

Owner must grant sudo/root, create a 0600 environment file, provide a
maintenance window and perform the Docker named-volume sub-drill without
touching the source volume. Container process-kill tests are not accepted.

Closure command:

```
python3 scripts/external_evidence.py validate --bundle docs/external-evidence/EXT-02.json
```

Current bundle: `pending`, `closure_allowed=false`.

## 4. EXT-03 / ACC-031 / G4 — exact closure evidence

Procedure: `docs/SECURITY-REVIEW-PACKAGE.md`; handover:
`docs/handover/EXT-03/README.md`.

Required artifacts: `rules-of-engagement.txt`, `scope.txt`, `findings.json`,
`scanner-output.txt`, `tls-scan.txt`, `signed-report.pdf`, `sign-off.txt`.

Required checks, all `true`: `scope_fully_executed`,
`no_open_critical_or_high`, `medium_findings_accepted`,
`remediations_retested`, `signed_go_decision`, `independent_reviewer`.

Required: an independent lead with no production write credentials, written
rules of engagement, staging deployment behind reviewed TLS ingress, test
identities for all four roles, signed report and owner acceptance. Internal
audits are explicitly not sufficient.

Closure command:

```
python3 scripts/external_evidence.py validate --bundle docs/external-evidence/EXT-03.json
```

Current bundle: `pending`, `closure_allowed=false`.

## 5. Public gate G1/G2/G3 — local validation and external evidence

| Gate | Local validation already executed | External evidence needed |
| --- | --- | --- |
| G1 TLS issuance/scan | `deploy/tls/nginx-tls.conf.example` present; `config_preflight.py --root .` passes `tls_template` | CA-issued certificate, TLS protocol/cipher/HSTS scan on the reviewed host |
| G2 segmentation | stack listeners `127.0.0.1:8000`/`8080`; preflight `backend_not_host_published` and `published_ports_loopback` pass | network topology/ACL/firewall evidence from the host owner |
| G3 ingress hardening | `frontend/nginx.conf` has `limit_conn`, `limit_req`, CSP and proxy headers; preflight `ingress_limits_and_proto` passes | deployed ingress configuration and hardening verification on the public edge |

Evidence file: `~/.market-mind-ops/ingress-gate-evidence.json`.

## 6. Public gate G5 — licensed data

Prepared: `docs/LICENSED-DATA-INVENTORY.md`, `docs/MARKET_DATA_LICENSING.md`,
`docs/DATA-LICENSING-GATE.md`, 5 gate tests and live
`/api/providers/status` (`no_live_provider_configured`).

External evidence needed: named provider/product, archived license terms,
written legal approval with approver/date, attested source ID, 0600 credential
location, archived post-configuration provider status.

## 7. Host reboot hook status (locally implemented)

Installed for the `jovyan` account:

- `~/.market-mind-ops/bootstrap.sh` — idempotent start/health entry point.
- `~/.market-mind-ops/shell-hook.sh` — guarded interactive-shell hook.
- sourced from `~/.bashrc` and `~/.profile`; opt out with `MM_NO_AUTOSTART=1`.
- root-level units remain as unprivileged artifacts in `scripts/host/`.

Locally verified: after killing the supervision loop and all four services,
opening one interactive shell restored a HEALTHY stack. This is the strongest
hook available without root; it is **not** host reboot evidence for EXT-02/G6.

## 8. Current authoritative score

Acceptance inventory: 37/40 = 92.5%. Public gates: 0/6. Overall production
readiness: 37/46 = 80.43%. No status was changed to verified without evidence.
