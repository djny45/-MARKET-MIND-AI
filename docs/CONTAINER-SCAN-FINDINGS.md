# Container image scan findings (2026-11-24)

CI job `container-security` builds both images and scans them with Trivy at
MEDIUM/HIGH/CRITICAL, `ignore-unfixed: false`, `exit-code: 1`. SARIF reports are
uploaded as artifact `container-image-scan-reports`. Findings are **not**
allowlisted or hidden: there is no `.trivyignore`, no severity downgrade and no
`continue-on-error` anywhere in the job.

## Current result: PASS

Run [45420717539](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45420717539)
on head `8785e468`: the container security job **PASSED** and all seven CI jobs
passed. Both images scanned clean at MEDIUM+:

| Image | Base | CRITICAL | HIGH | MEDIUM | LOW / unknown |
| --- | --- | --- | --- | --- | --- |
| backend | `python:3.12.16-alpine3.24` | 0 | 0 | 0 | 0 |
| frontend | `nginxinc/nginx-unprivileged:1.31.7-alpine3.24-slim` | 0 | 0 | 0 | 0 |

This is a genuine scan of a populated image, not a silent skip: the log records
`Detected OS family="alpine" version="3.24.4"`, `[alpine] Detecting
vulnerabilities... pkg_num=38` and `[python-pkg] Detecting vulnerabilities...`,
so both an OS package set and the Python environment were enumerated.

## Base-image comparison (identical scanner and gate)

All counts below come from the same job definition, Trivy v0.70.0, severity
MEDIUM,HIGH,CRITICAL, `ignore-unfixed: false`, `exit-code: 1`. Only the backend
base image varied.

| Backend base | MEDIUM+ | Breakdown | OS findings with a fixed version | Verdict |
| --- | --- | --- | --- | --- |
| `python:3.12-slim` (Debian 13.8) | **137** | 1 CRITICAL / 58 HIGH / 78 MEDIUM | **0 of 129** | rejected — unfixable |
| `python:3.12-slim-bookworm` (Debian 12) | **261** | 109 HIGH / 152 MEDIUM | 0 | rejected — substantially worse |
| `cgr.dev/chainguard/python:latest` | **8** | 1 CRITICAL / 5 HIGH / 2 MEDIUM | 8 of 8 | rejected — unpinnable |
| `python:3.14-alpine3.24` (unpinned venv) | **15** | 1 CRITICAL / 5 HIGH / 9 MEDIUM | 8 of 8 (OS) | superseded |
| `python:3.12.16-alpine3.24` (multi-stage, no pip) | **0** | — | — | **adopted** |

Evidence runs: Debian 13 `45388655934`, Debian 12 `45387123716`, Chainguard
`45393434376`, Alpine unpinned `45391374304`, intermediate multi-stage
`45410124590` (134 MEDIUM+), inherited-pip Alpine `45418397211` (5 MEDIUM+),
final `45420717539` (0).

### Why Chainguard was rejected despite the second-best count

Chainguard was genuinely attractive at 8 findings, but:

- Its free tier publishes **only `latest` and `latest-dev`** (verified against
  the registry tag list, which otherwise contains just sigstore sidecars). A
  floating tag trips the `DS-0001` Dockerfile misconfiguration at MEDIUM and
  makes builds non-reproducible.
- It ships **Python 3.15**, while CI tests 3.12 and the project targets 3.12.
- The one failure in its run was not the base image: `/api/ready` returned 503
  because the Dockerfile never created `/data`. That was an authoring bug, and
  it is fixed in the adopted image.

## Root cause of the Python findings (correcting an earlier note)

An earlier version of this document claimed the `certifi`/`msgpack`/`urllib3`/
`setuptools` findings were Debian-packaged duplicates. That was wrong.

They were **pip's vendored copies**: `setuptools 70.3.0` matches
`pip/_vendor/vendor.txt` exactly, and the vendored `certifi`/`msgpack`/`urllib3`
track pip's bundle, not the installed distributions. Any
`pip install --upgrade certifi==…` therefore could not clear them, which is why
the pins appeared to do nothing.

Remediation: the runtime image is multi-stage and installs nothing, so both the
builder venv and the base image's system `pip` are removed
(`pip`, `setuptools`, `pkg_resources`, `_distutils_hack`,
`distutils-precedence.pth`). This was proven safe first: `app.main` imports,
registers 153 routes, and serves `/api/ready` and `/api/health` with 200 while
those packages are absent, and nothing under `backend/app` imports pip or
setuptools.

The intermediate run `45410124590` is the evidence that pip removal actually
worked: all Python-origin findings went to zero, but the image still reported
5 MEDIUM because the **base image's own** `pip 25.0.1` under
`/usr/local/lib/python3.12` had not yet been removed. Removing that closed the
remaining findings in `45420717539`.

## What changed in the backend image

- Base moved to the fully pinned `python:3.12.16-alpine3.24` (versioned tag, so
  `DS-0001` is satisfied and rebuilds are reproducible).
- Multi-stage: dependencies are installed in a builder stage; the runtime stage
  receives only the venv, the application and the operator scripts.
- `apk upgrade --no-cache` refreshes Alpine packages. At scan time `libcrypto3`,
  `libssl3` and `zlib` had fixes available in `3.5.9-r1` / `1.4-r0`; the
  unpinned Alpine run reported 8 such MEDIUM findings, all fixable, and the
  final image reports none.
- Runtime pip/setuptools removed (see above).
- `/data` created and owned by the non-root `appuser` (UID 10001); the process
  runs unprivileged, matching the existing `no-new-privileges` and `cap_drop:
  ALL` Compose settings.
- All compiled dependencies (`pydantic-core`, `cryptography`, `uvloop`,
  `httptools`, `watchfiles`, `pyyaml`, `websockets`, `cffi`, `rpds-py`) publish
  `musllinux` cp312 wheels, so no compiler toolchain is needed and the build
  does not depend on `apk add`ing build deps.

## Disposition

- **Not suppressed.** No ignore file, severity downgrade or `continue-on-error`
  was added at any point.
- **Genuinely remediated.** The 137 MEDIUM+ findings on the Debian base are gone
  rather than hidden: 129 of them had no fixed version on Debian 13, and the
  Alpine base does not ship those packages at all.
- **Scan evidence, not a security approval.** This closes the container-image
  gate only. Independent review (ACC-031 / EXT-03) remains BLOCKED, and a future
  base-image rebuild must re-run the same failing-closed job.
