# Trivy / CI security audit — 2026-11-22

Read-only audit of the existing Trivy CI configuration plus a locally executed
Trivy scan. No workflow file was edited and no check was suppressed or bypassed.
Research-only platform: no trading, wallet, signing or order routing involved.

## 1. Tool installation (local, under /tmp)

`trivy` was absent from the container. It was installed from the upstream
installer into `/tmp` (nothing installed system-wide):

```
$ curl -fsSL --max-time 25 https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh -o /tmp/opencode/trivy-install.sh
$ mkdir -p /tmp/opencode/trivy-bin && sh /tmp/opencode/trivy-install.sh -b /tmp/opencode/trivy-bin
aquasecurity/trivy info checking GitHub for latest tag
aquasecurity/trivy info found version: 0.76.2 for v0.76.2/Linux/64bit
aquasecurity/trivy info installed /tmp/opencode/trivy-bin/trivy
$ /tmp/opencode/trivy-bin/trivy --version
Version: 0.76.2
```

`docker` remains ABSENT (`command -v docker` → nothing), so container runtime
verification of findings is BLOCKED locally.

## 2. Filesystem scan (exact command and result)

```
$ cd /tmp/opencode/MARKET-MIND-AI-target
$ export TRIVY_CACHE_DIR=/tmp/opencode/trivy-cache
$ /tmp/opencode/trivy-bin/trivy fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL .
```

Exit code: `FS_EXIT=0` (raw Trivy defaults to `exit-code=0`; the GitHub Action in
CI sets `exit-code: '1'`, so findings there would fail the job).

Verbatim summary:

```
Report Summary

┌────────────────────────────┬────────────┬─────────────────┬───────────────────┬─────────┐
│           Target           │    Type    │ Vulnerabilities │ Misconfigurations │ Secrets │
├────────────────────────────┼────────────┼─────────────────┼───────────────────┼─────────┤
│ frontend/package-lock.json │    npm     │        0        │         -         │    -    │
├────────────────────────────┼────────────┼─────────────────┼───────────────────┼─────────┤
│ backend/Dockerfile         │ dockerfile │        -        │         0         │    -    │
├────────────────────────────┼────────────┼─────────────────┼───────────────────┼─────────┤
│ frontend/Dockerfile        │ dockerfile │        -        │         1         │    -    │
└────────────────────────────┴────────────┴─────────────────┴───────────────────┴─────────┘
```

Verbatim finding:

```
frontend/Dockerfile (dockerfile)
================================
Tests: 24 (SUCCESSES: 23, FAILURES: 1)
Failures: 1 (MEDIUM: 0, HIGH: 1, CRITICAL: 0)

DS-0002 (HIGH): Specify at least 1 USER command in Dockerfile with non-root user as argument
Running containers with 'root' user can lead to a container escape situation. It is a best practice to run containers as non-root users, which can be done by adding a 'USER' statement to the Dockerfile.
See https://avd.aquasec.com/misconfig/ds-0002
```

No vulnerabilities and no secrets were reported at MEDIUM/HIGH/CRITICAL.

Full output retained at `/tmp/opencode/trivy-fs.txt`.

After the new DR scripts and documentation were added, the identical filesystem
scan was re-run to confirm no new finding was introduced by this work. Result:
the same single HIGH `frontend/Dockerfile` DS-0002 and no other MEDIUM/HIGH/
CRITICAL findings (`POST_CHANGE_FS_EXIT=0`, raw Trivy default). No secret was
detected in `scripts/` or the new docs.

## 3. Config scan (exact command and result)

```
$ export TRIVY_CACHE_DIR=/tmp/opencode/trivy-cache
$ /tmp/opencode/trivy-bin/trivy config .
```

Exit code: `CONFIG_EXIT=0`.

Verbatim summary:

```
Report Summary

┌─────────────────────┬────────────┬───────────────────┐
│       Target        │    Type    │ Misconfigurations │
├─────────────────────┼────────────┼───────────────────┤
│ backend/Dockerfile  │ dockerfile │         1         │
├─────────────────────┼────────────┼───────────────────┤
│ frontend/Dockerfile │ dockerfile │         2         │
└─────────────────────┴────────────┴───────────────────┘
```

Findings:

```
backend/Dockerfile (dockerfile)
DS-0026 (LOW): Add HEALTHCHECK instruction in your Dockerfile
See https://avd.aquasec.com/misconfig/ds-0026

frontend/Dockerfile (dockerfile)
Tests: 27 (SUCCESSES: 25, FAILURES: 2)
Failures: 2 (UNKNOWN: 0, LOW: 1, MEDIUM: 0, HIGH: 1, CRITICAL: 0)

DS-0002 (HIGH): Specify at least 1 USER command in Dockerfile with non-root user as argument
DS-0026 (LOW): Add HEALTHCHECK instruction in your Dockerfile
```

Full output retained at `/tmp/opencode/trivy-config.txt`.

## 4. Finding triage and fixes needed elsewhere

| ID | Severity | Exact location | Triage | Action |
|----|----------|----------------|--------|--------|
| DS-0002 | HIGH | `frontend/Dockerfile:10-13` (no `USER` instruction; base image at line 10 is `nginxinc/nginx-unprivileged:stable-alpine`) | Likely false positive: the unprivileged base image is designed to run as non-root, but Trivy's static Dockerfile check does not inherit the base image's `USER`. NOT verified locally because `docker` is absent. | Owner of `frontend/Dockerfile` should add `USER 101` after line 10 (or before `EXPOSE 8080`) and verify with `docker run --rm <image> id`. Do **not** suppress the check. |
| DS-0026 | LOW | `backend/Dockerfile:1-18` and `frontend/Dockerfile:1-13` | Expected: health checks are defined at the Compose level in `docker-compose.yml` (`healthcheck:` blocks for `backend` and `frontend`), not in the Dockerfiles. | Owner may add `HEALTHCHECK` to the Dockerfiles or accept with documented rationale. Not a MEDIUM/HIGH/CRITICAL gate. |
| Lockfile gap | n/a | `frontend/package-lock.json` is UNTRACKED (`git ls-files frontend/package-lock.json` → empty) | The local scan found 0 npm vulnerabilities because an untracked lockfile exists locally. The `trivy-security` job checks out a clean tree and does not run `npm install`, so in CI there is no lockfile for Trivy to scan. | Owner should commit `frontend/package-lock.json` (or add an `npm install --package-lock-only` step to the scan job). No vulnerability was hidden locally by this, but the CI npm scan is effectively empty. |

I did **not** modify `frontend/Dockerfile`, `backend/Dockerfile`,
`docker-compose.yml` or any workflow file: they are outside this agent's file
ownership. No Trivy result was ignored, downgraded or suppressed to make a job
green.

## 5. Existing workflow inspection (read-only)

`.github/workflows/quality.yml` already contains a Trivy job on `main`:

- Lines 367-383: `trivy-security` job,
  `uses: aquasecurity/trivy-action@v0.36.0`,
  `scan-type: fs`, `scan-ref: .`,
  `scanners: vuln,secret` (line 380),
  `severity: HIGH,CRITICAL` (line 381),
  `ignore-unfixed: true` (line 382),
  `exit-code: '1'` (line 383).
- Latest `main` run observed: `gh run list --workflow quality.yml --limit 3`
  shows `completed success ... main push 45055399975`.

Gaps versus the requested local scan:

1. `misconfig` is not in `scanners` (line 380), so DS-0002 above is invisible to
   CI. Adding misconfig will make the job fail until DS-0002 is genuinely fixed
   or confirmed false-positive with evidence — that is the correct outcome, not
   a reason to weaken the check.
2. `severity` is `HIGH,CRITICAL` (line 381), not `MEDIUM,HIGH,CRITICAL`.
3. There is no `trivy config .` step.
4. No lockfile is created/committed before the scan (see lockfile gap above).

Recommended workflow change (NOT APPLIED — see blocker in section 7): at line
380 use `scanners: vuln,misconfig,secret`; at line 381 use
`severity: MEDIUM,HIGH,CRITICAL`; add a second step
`run: trivy config .` (installed via the same action or an explicit setup) so
Dockerfile misconfigurations are gated. Fix DS-0002 first.

## 6. `feat/trivy-fs` branch inspection (read-only)

`REMAINING_WORK.md` sections 8-9 claim a locally committed `feat/trivy-fs`
branch with commit `1827be8` and a `docs/TRIVY-CI.md` document. In this checkout
none of those exist:

```
$ git branch -a --list '*trivy*'
(end — no output)
$ git ls-remote --heads origin '*trivy*'
(end — no output)
$ git show --stat --oneline 1827be8
fatal: ambiguous argument '1827be8': unknown revision or path not in the working tree.
$ git show --stat --oneline 77467d0
fatal: ambiguous argument '77467d0': unknown revision or path not in the working tree.
$ ls docs/TRIVY-CI.md
NO docs/TRIVY-CI.md
```

Therefore the contents of that branch could not be inspected or compared; this
audit uses the actual `main` workflow instead. Historical commits on the
current `main` history mentioning Trivy (`303ea8a6`, `4ed36758`, `ab3ea2ee`,
`6470271f`) were identified via `git log --all --oneline --grep=trivy -i` but
the missing branch itself is unavailable here.

## 7. OAuth `workflow` scope blocker and precise remedy

```
$ gh auth status
github.com
  ✓ Logged in to github.com account djny45 (/home/jovyan/.config/gh/hosts.yml)
  - Active account: true
  - Git operations protocol: https
  - Token: gho_************************************
  - Token scopes: 'gist', 'read:org', 'repo'
```

There is no `workflow` scope. GitHub rejects pushes that modify
`.github/workflows/*` with such a token, even though `repo` allows other
pushes. No workflow push was attempted in this task.

Remedy (choose one, performed by the repository owner):

1. Create a Personal Access Token with the `workflow` scope (classic PAT:
   select `repo` + `workflow`; fine-grained PAT: grant repository
   `djny45/-MARKET-MIND-AI` "Workflows: read and write" plusContents: read/write),
   then re-authenticate locally, e.g.
   `gh auth login --scopes workflow` / `gh auth refresh -h github.com -s workflow`,
   and retry the push. Or:
2. In GitHub Settings → Applications → Authorized OAuth Apps, authorize the
   OAuth application used by the CLI for the `workflow` permission, then
   re-authenticate (`gh auth refresh -h github.com -s workflow`).

Even after the scope is granted, a branch-protection rule or an environment
approval may still be required before workflow changes land on `main`.

## 8. Commands run (complete list)

```
command -v docker trivy curl python3 node npm gh
curl -fsSL --max-time 25 https://raw.githubusercontent.com/aquasecurity/trivy/main/contrib/install.sh -o /tmp/opencode/trivy-install.sh
mkdir -p /tmp/opencode/trivy-bin && sh /tmp/opencode/trivy-install.sh -b /tmp/opencode/trivy-bin
/tmp/opencode/trivy-bin/trivy --version
TRIVY_CACHE_DIR=/tmp/opencode/trivy-cache /tmp/opencode/trivy-bin/trivy fs --scanners vuln,misconfig,secret --severity MEDIUM,HIGH,CRITICAL .
TRIVY_CACHE_DIR=/tmp/opencode/trivy-cache /tmp/opencode/trivy-bin/trivy config .
cat -n frontend/Dockerfile
cat -n backend/Dockerfile
grep -n -A16 'trivy-security:' .github/workflows/quality.yml
git branch -a --list '*trivy*'
git ls-remote --heads origin '*trivy*'
git show --stat --oneline 1827be8
git show --stat --oneline 77467d0
git log --all --oneline --grep=trivy -i
git ls-files frontend/package-lock.json
git ls-files .github/workflows/
gh auth status
gh run list --workflow quality.yml --limit 8
```

Evidence files: `/tmp/opencode/trivy-fs.txt`, `/tmp/opencode/trivy-config.txt`,
`/tmp/opencode/trivy-gh-evidence.txt`.
