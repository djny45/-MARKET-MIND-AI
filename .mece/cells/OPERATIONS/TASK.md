# OPERATIONS cell — CI, containers, and operational readiness

Read `AGENTS.md` first. Inspect `.github/**`, `docker-compose.yml`, `.dockerignore`, `SECURITY.md`, and `CONTRIBUTING.md` before changing anything.

## Exclusive ownership
You may edit only `.github/**`, `docker-compose.yml`, `.dockerignore`, `SECURITY.md`, and `CONTRIBUTING.md`. Do not edit `backend/**`, `frontend/**`, `docs/**`, `AGENTS.md`, or `PROJECT_STATUS.md`. Write your final report to `.mece/cells/OPERATIONS/REPORT.md`.

## Task
Audit the repository's CI and private Docker Compose operating path for one high-impact, low-risk improvement within your ownership. Prefer clearer verification, safer workflow permissions/concurrency, container health/restart behavior, repeatable backup/restore instructions in existing owned documentation, or diagnostics that do not leak secrets.

## Constraints
- Keep the backend internal-only; never publish its port.
- Preserve non-root execution, dropped capabilities, no-new-privileges, resource limits, security headers, and dependency audits.
- No public deployment, external cloud mutation, production host changes, or credential creation.
- Do not add an AI workflow that requires a paid model API. Do not add Vercel.
- Do not remove tests/checks merely to obtain green CI.
- A host-specific recovery drill, TLS/DNS setup, authentication model, or external alerting target requires a human decision; document the missing decision in your report instead of guessing.

## Verification
Validate workflow/config syntax, run relevant Docker Compose validation and existing checks where available, and inspect changes for secret leakage and permission escalation. Report exact commands/results and every unverified environment-specific item.
