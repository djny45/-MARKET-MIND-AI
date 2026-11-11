# FRONTEND cell — integration and UI quality

Read `AGENTS.md` first. Inspect the existing React/Vite application and its current scripts before editing.

## Exclusive ownership
You may edit only `frontend/**`. Do not edit root files, `.github/**`, `backend/**`, or `docs/**`. Write your final report to `.mece/cells/FRONTEND/REPORT.md`.

## Task
Audit the existing frontend for the highest-impact, concrete correctness gap that can be fixed entirely within `frontend/**`. Focus on API integration, loading/empty/error states, chart/data labelling, keyboard accessibility, and preventing synthetic or stale data from being presented as live.

Implement only a bounded improvement that fits the existing React/Vite architecture. Avoid a redesign or dependency-heavy rewrite.

## Constraints
- Do not add brokerage screens, order-entry flows, live execution, or personalized investment recommendations.
- Preserve explicit synthetic-data labelling and freshness/provenance disclosures.
- Do not invent live provider data or hide provider-unavailable states.
- Do not add Vercel-specific code or deployment configuration.
- If backend contract changes are required, stop and report the contract mismatch rather than editing outside your ownership.

## Verification
For code fixes, write a regression test first and confirm it fails for the expected reason before implementing. Run the complete frontend test suite if one exists and always run the production build. Report exact commands, results, changed paths, and remaining gaps.
