# Container image scan findings (2026-11-24)

The new CI `container-security` job builds both images and scans them with
Trivy at MEDIUM/HIGH/CRITICAL, `ignore-unfixed: false`, `exit-code: 1`. SARIF
reports are uploaded as artifact `container-image-scan-reports`. Findings are
**not** allowlisted or hidden.

## Observed result

Final CI run [45380741384](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45380741384)
on head `964dcead`: the **Container image security scan job FAILED** on backend
findings only; the other six jobs passed. The frontend image now has **zero**
MEDIUM+ findings after pinning `nginxinc/nginx-unprivileged:1.31.7-alpine3.24-slim`
and upgrading Alpine packages. Both SARIF reports were collected:

| Image | HIGH | MEDIUM | LOW / unknown |
| --- | --- | --- | --- |
| backend | 59 | 78 | 95 |
| frontend | 0 | 0 | 0 |

The first run [45373686192](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45373686192)
on `900a9c36` reported backend 53 HIGH / 81 MEDIUM / 94 LOW-unknown; an
intermediate run reported frontend 20 HIGH / 13 MEDIUM before the patched nginx
tag was pinned. We also evaluated `python:3.12-slim-bookworm` (Debian 12) in CI
run [45387123716](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45387123716):
it produced **109 HIGH / 152 MEDIUM / 135 LOW-unknown**, substantially worse
than the current Debian 13-based `python:3.12-slim` (59/78/95), so it was
reverted. The backend count reflects a refreshed Trivy database; the gate
remains failing.

Affected OS packages include `bsdutils`, `util-linux`, `libblkid1`,
`libmount1`, `libuuid1`, `openssl`/`libssl3t64`, `libsqlite3-0`, `ncurses`,
`systemd` libraries, `perl-base`, `libacl1` and GCC runtime libraries from the
`python:3.12-slim` base image (Debian 13.8). Most report **no fixed version** in
Trivy's database, so an in-image `apt upgrade` cannot resolve them today.
Python `pip` 25.0.1 had five MEDIUM findings with fixed versions, so the backend
Dockerfile now upgrades to `pip==26.2.0`; `certifi`, `msgpack`, `setuptools` and
`urllib3` are also pinned to fixed releases. The final SARIF still reports those
Python packages at the older installed versions, consistent with Debian-packaged
duplicates in the base image rather than the pip-installed copies. No further
safe in-image remediation was identified without changing the base distribution,
so those findings are preserved rather than suppressed.

The frontend scan step is marked `if: always()` so its SARIF is still collected
after a backend failure; the job remains failed because the scans are real
gates.

## Disposition

- **Not suppressed.** No Trivy ignore file, severity downgrade or
  `continue-on-error` was added to make CI green.
- **Partially remediated.** The fixable `pip` findings are addressed in the
  Dockerfile; the base-image OS findings remain an external dependency on
  upstream Debian/Python base images.
- **Required follow-up.** Rebuild on a patched base image when Debian publishes
  fixes, and rerun the same failing-closed job. Until then the container
  security gate remains **FAIL** and public deployment is not authorized.

This is CI evidence, not an independent security approval; ACC-031 stays BLOCKED.
