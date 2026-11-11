# Cell FRONTEND — Read-only frontend audit

Read AGENTS.md and load the stageshow skill only if inspecting UI mockups or visual storytelling; otherwise do not load unrelated skills. Inspect frontend source, tests, package manifests, build configuration and API integration only.

Do not edit files, install packages, or deploy.

Assess:
- App structure, route/state organization and component boundaries.
- API client contracts, loading/error/empty states and data freshness display.
- Accessibility, responsive behavior and security-sensitive rendering.
- Dependency health and production build/test commands.
- Whether synthetic/historical data is clearly distinguished from current data.

Run safe checks only when dependencies are already installed. Record exact commands and outputs.

Write .mece/cells/FRONTEND/REPORT.md with summary, inspected paths, evidence, commands/results, prioritized findings, blockers, residual risks, and confirmation that no source files changed.