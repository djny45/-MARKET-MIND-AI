# BACKEND cell — reliability and regression coverage

Read `AGENTS.md` first, then inspect `.agents/skills/rea/README.md` and load only the playbook relevant to the backend task.

## Exclusive ownership
You may edit only `backend/**`. Do not edit root files, `.github/**`, `frontend/**`, or `docs/**`. Write your final report to `.mece/cells/BACKEND/REPORT.md`.

## Task
Audit the FastAPI backend and its tests against the current behavior described in `PROJECT_STATUS.md`. Identify the most important concrete backend reliability or regression-coverage gap that can be completed entirely within `backend/**`, then implement the smallest safe improvement.

Prioritize data integrity, schema/migration safety, backup/restore correctness, data provenance, API error handling, and protection against misleading freshness/provider status. Avoid broad refactors.

## Constraints
- No live-provider integration, credentials, network scraping, broker connectivity, or trading execution.
- Keep synthetic fixtures explicitly labelled.
- Do not claim readiness proves live-data availability.
- Do not remove or weaken safety assertions, audit/provenance checks, or existing tests.
- If the only remaining issue needs a user/provider/host decision, do not guess; report the blocker without implementing it.

## Verification
Write the failing regression test first for any code bug, verify the expected failure, then make the minimal fix. Run the full backend test suite and relevant compile/API smoke checks. Report exact commands, pass/fail counts, changed paths, and anything not verified.
