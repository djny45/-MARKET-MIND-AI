# Contributing

Thank you for helping improve MARKET-MIND-AI.

## Before opening a pull request
- Open an issue for substantial features or architectural changes.
- Keep changes focused and document the reason for the change.
- Add or update tests for every behavior change.
- Update relevant documentation and the roadmap.
- Include source provenance, freshness, and licensing details for data integrations.
- Do not commit API keys, credentials, personal data, or proprietary datasets.

## Engineering expectations
- Prefer typed contracts and small, composable modules.
- Keep deterministic calculations independent from language-model output.
- Make worker inputs, outputs, assumptions, and failure modes explicit.
- Reject unsupported or invalid workflow states rather than silently guessing.
- Add tests for missing data, malformed data, and boundary conditions.
- Pin or constrain dependencies and review their licences.

## Pull request checklist
- [ ] Tests pass locally.
- [ ] Documentation is updated.
- [ ] No secrets or restricted data are included.
- [ ] New dependencies have been reviewed.
- [ ] Data-provider terms and attribution requirements are documented.
- [ ] UI changes include a clear description and screenshots where useful.


## Product and data boundaries

- Keep this repository focused on historical market research, evidence quality, provenance, and reproducibility.
- Do not add brokerage credentials, order routing, automated trading, or paper-trading workflows.
- Never present synthetic fixtures as real market observations.
- Preserve source labels, status, timestamps, and known limitations. Do not invent observations or silently fill missing bars.
- Prefer a single central research core with explicit, testable analytical modules. Worker catalogue entries are templates unless their execution is implemented and tested.

## Local validation

Requirements: Python 3.11+, Node.js 20+, and npm.

Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=. python -m unittest discover -s tests -v
```

Frontend:
```bash
cd frontend
npm install
npm run build
```

## Analytical standards

- Require timezone-aware timestamps and validate OHLCV envelopes.
- Keep historical, delayed, live, and synthetic statuses distinct.
- Use exact timestamp alignment where synchronized observations are required; report sample counts and insufficient-data cases.
- Treat statistical flags and chart patterns as descriptive review aids, not predictions.
- Test missing, malformed, duplicate, out-of-order, and non-finite values where applicable.
- Explain methodology limitations, provider schedules, licensing, and data-entitlement assumptions.

## Security and licensing

- Use environment variables for local configuration and safe example values only.
- Review dependency licences and provider terms before adding dependencies or data sources.
- Treat imported files and external feed content as untrusted input.
- Report security issues privately to repository maintainers rather than publishing exploit details in an issue.
