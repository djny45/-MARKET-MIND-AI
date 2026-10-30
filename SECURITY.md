# Security Policy

## Supported versions
Security fixes are applied to the latest version on the default branch.

## Reporting a vulnerability
Please do not publish exploitable details in a public issue. Contact the repository owner through GitHub's private vulnerability reporting feature, if enabled, or use a private communication channel available on the owner's GitHub profile.

Include:
- A concise description and impact.
- Reproduction steps or a proof of concept that does not expose real credentials or user data.
- Affected files, versions, and environment.
- Suggested mitigation, if known.

## Security expectations
- Never commit credentials, tokens, private keys, or broker secrets.
- Treat market feeds, news, documents, and uploaded files as untrusted input.
- Use least-privilege access for data providers.
- Validate external payloads and apply request limits.
- Keep dependencies updated and review security advisories.
- Do not add broker execution or order-routing functionality to this research project.
