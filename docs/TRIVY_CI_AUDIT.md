# Trivy / CI security audit — updated 2026-11-23

Read-only audit plus a local scan. No check was suppressed or bypassed.
Research-only platform: no trading, wallet, signing or order routing.

## Local tool and scans

`trivy` 0.76.2 was installed under `/tmp/opencode/trivy-bin` (nothing installed
system-wide). `docker` remains absent.

CI-equivalent filesystem scan (local-only, git-excluded `third_party/` and
`.venvs/` skipped because a clean CI checkout does not contain them):

```
TRIVY_CACHE_DIR=/tmp/opencode/trivy-cache /tmp/opencode/trivy-bin/trivy fs \
  --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL \
  --skip-dirs third_party --skip-dirs .venvs .
```

Result: **0 vulnerabilities, 0 misconfigurations, 0 secrets** at
MEDIUM/HIGH/CRITICAL. `frontend/Dockerfile` contains `USER 101`, so the
historical DS-0002 HIGH finding is resolved, not suppressed.

`trivy config .` on the full local tree reports DS-0002 HIGH only in
`third_party/freqtrade/docker/Dockerfile.plot`, which is excluded from git and
absent in CI. DS-0026 (LOW, missing `HEALTHCHECK` in Dockerfiles) is below the
agreed severity gate; Compose defines health checks at the service level.

## Corrections to the previous version of this document

- `frontend/package-lock.json` is **tracked** (commit `5f0f0b35`); the previous
  "untracked lockfile" claim is stale.
- `frontend/Dockerfile` already has `USER 101`; the old "add USER 101" action
  is complete.
- `feat/trivy-fs`, commits `1827be8`/`77467d0` and `docs/TRIVY-CI.md` **do
  exist** locally; the previous "do not exist" claim was stale.
- The old "latest CI run 45055399975" is superseded by runs recorded in
  `FINAL_TEST_RESULTS.md`.

## CI workflow gap and implemented fix

On `origin/main`, `.github/workflows/quality.yml` `trivy-security` used
`scanners: vuln,secret` and `severity: HIGH,CRITICAL` with `ignore-unfixed: true`.

The expanded job is committed on the local-only branch
`security/trivy-ci-scope` (`0c89aa68`):

- `scanners: vuln,misconfig,secret`
- `severity: MEDIUM,HIGH,CRITICAL`
- `ignore-unfixed: false` (do not suppress unfixed findings)
- `exit-code: '1'`
- second `trivy-action` step with `scan-type: config`, MEDIUM+ severity,
  `exit-code: '1'`, and `skip-setup-trivy: true`
- job permissions remain least-privilege `contents: read`

`backend/tests/test_ci_workflow_config.py` on that branch asserts all of the
above plus workflow indentation/no tabs and least-privilege permissions.

## Permission blocker (owner action required)

`gh auth status` reports token scopes `gist`, `read:org`, `repo` — no
`workflow`. GitHub rejects pushes that modify `.github/workflows/*` with this
token. Therefore the workflow commit was isolated on `security/trivy-ci-scope`
so the main audit branch remains pushable.

Owner remedy (do not bypass):

```
gh auth refresh -h github.com -s workflow
# approve the device code at https://github.com/login/device
```

Then push `security/trivy-ci-scope`, open/merge the workflow change through the
normal authorized path, and confirm the expanded Trivy job passes on the target
branch. Never commit a PAT, force-push, or suppress checks to obtain a green run.

## CI run evidence from the baseline

Success: <https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45057999583>
(commit `4abfa3da`, all five jobs). Failure that was genuinely fixed by a
dependency upgrade: <https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45057550963>
(Vitest 2.x advisories; fixed by upgrading Vitest/Vite, not by weakening the
audit gate). No new CI run is claimed for the workflow branch because it has
not been pushed.
