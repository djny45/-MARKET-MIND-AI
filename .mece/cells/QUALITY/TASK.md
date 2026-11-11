# Cell QUALITY — Read-only CI and test audit

Read AGENTS.md and the relevant REA CI/test audit playbook. Inspect CI workflows, test suites, lint/type-check configuration, dependency manifests and lockfiles.

Do not edit workflow files, install dependencies, or change application code.

Assess:
- CI job coverage, triggers, permissions, caching and artifact handling.
- Backend/frontend test, lint, type-check and build coverage.
- Dependency audit/SBOM coverage and pinning/reproducibility.
- Missing regression, migration, integration and failure-path tests.
- Whether latest workflow evidence matches current HEAD; distinguish historical runs from current verification.

Run safe checks only when prerequisites already exist. Report exact commands, exit codes and relevant output.

Write .mece/cells/QUALITY/REPORT.md with paths/evidence, CI/test map, gaps by priority, blockers and residual risks. No source changes.