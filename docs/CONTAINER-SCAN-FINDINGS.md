# Container image scan findings (2026-11-24)

The new CI `container-security` job builds both images and scans them with
Trivy at MEDIUM/HIGH/CRITICAL, `ignore-unfixed: false`, `exit-code: 1`. SARIF
reports are uploaded as artifact `container-image-scan-reports`. Findings are
**not** allowlisted or hidden.

## Observed result

CI run [45373686192](https://github.com/djny45/-MARKET-MIND-AI/actions/runs/45373686192)
on `900a9c36`: the **Container image security scan job FAILED** on the backend
image; the other six jobs passed. The backend SARIF contained:

| SARIF level | Trivy severity | Count |
| --- | --- | --- |
| error | HIGH | 53 |
| warning | MEDIUM | 81 |
| note | LOW / unknown | 94 |

Affected OS packages include `bsdutils`, `util-linux`, `libblkid1`,
`libmount1`, `libuuid1`, `openssl`/`libssl3t64`, `libsqlite3-0`, `ncurses`,
`systemd` libraries, `perl-base`, `libacl1` and GCC runtime libraries from the
`python:3.12-slim` base image (Debian 13.8). Most report **no fixed version** in
Trivy's database, so an in-image `apt upgrade` cannot resolve them today.
Python `pip` 25.0.1 had five MEDIUM findings with fixed versions, so the backend
Dockerfile now upgrades to `pip==26.2.0`.

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
