# Cell BACKEND — Read-only backend audit

Read AGENTS.md and the relevant REA playbook for CI/test audit or tool design before proceeding. Inspect backend source, tests, schemas, migrations and API routes only.

Do not edit files or access secrets. Do not enable brokerage/execution functionality.

Assess:
- Backend architecture and module boundaries.
- API contract consistency, validation, error handling and health/readiness semantics.
- Database schema/migration safety and transaction behavior.
- Test coverage, missing edge cases and reproducibility.
- Data provenance and synthetic-data labelling at backend boundaries.

Run only safe, non-mutating inspection/test commands when dependencies are already available. Record exact commands and outcomes; do not install packages or alter databases.

Write .mece/cells/BACKEND/REPORT.md with: summary, inspected paths, evidence (paths/line references), commands and results, prioritized findings, blockers, residual risks, and "read-only audit; no source files changed".