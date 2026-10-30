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
