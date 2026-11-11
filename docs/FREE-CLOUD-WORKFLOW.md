# Free cloud development workflow

This repository is public and has a GitHub Actions quality workflow at
`.github/workflows/quality.yml`. It runs backend tests and API smoke checks,
the frontend production build, Docker Compose integration checks, and
dependency audits when code is pushed directly to `main`, `feat/**`, or
`feature/**`, and when a pull request targets `main`. It can also be started
manually and runs on a weekly schedule.

## Enabled automation

- Dependabot checks Python dependencies in `backend/` weekly.
- Dependabot checks npm dependencies in `frontend/` weekly.
- Dependabot checks GitHub Actions versions weekly.
- Version-update pull requests are capped at five concurrently: two for Python,
  two for npm, and one for GitHub Actions. Security-update pull requests are
  handled separately and are not limited by `open-pull-requests-limit`.
- Dependency update pull requests are validated by the existing quality workflow.
- GitHub Actions standard runners are free for public repositories.

## Safe contribution loop

1. Open a focused issue describing one bounded change and acceptance criteria.
2. Create a feature branch; do not commit directly to `main`.
3. Implement the change and add or update tests.
4. Open a pull request.
5. Wait for the existing quality workflow and dependency audit to finish.
6. Review the diff, test evidence, and dependency changes before merging.

## Important AI-agent limitation

GitHub MCP is a repository integration, not an AI coding model. GitHub Actions
provides cloud CI compute, not a continuously running code-writing agent.
A fully free autonomous coding agent also needs an inference provider or a
self-hosted model runtime. Free hosted model quotas and availability can change;
this repository does not assume a paid API, store model credentials, or run
unreviewed AI-generated changes on the default branch.

A free model provider or self-hosted model runtime can be added later as a
separate, permission-limited PR author after its usage limits, credential
handling, and repository permissions are verified. Keep human review and the
existing CI gates.

## Scope and security

- Do not add brokerage credentials or trading execution to CI.
- Never place API keys in workflow YAML, source files, issues, or logs.
- Use GitHub repository secrets only for credentials that are genuinely needed.
- Keep changes on branches and require review before merging.
- The application remains a research-only workspace; this workflow does not
  enable brokerage execution or public production deployment.
