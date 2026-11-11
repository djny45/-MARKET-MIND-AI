# Cell SECURITY — Read-only security audit

Read AGENTS.md and relevant REA quality guidance. Inspect configuration templates, Docker/Compose, HTTP security, auth boundaries, dependency/security workflows and secret-handling patterns.

Never print or copy secret values. Do not inspect credential contents, access external systems, or change configuration.

Assess:
- Secret exposure risks using filenames/pattern checks only; redact all matches.
- Authentication/authorization boundaries and whether public exposure is safe.
- Network binding, published ports, TLS assumptions, headers, CORS and request limits.
- Container least privilege, capabilities, filesystem and resource constraints.
- Untrusted market/news input handling and injection risks.
- Dangerous execution paths; confirm brokerage/order execution remains unavailable and disabled.

Write .mece/cells/SECURITY/REPORT.md with evidence, redacted findings, safe checks run, severity, remediation recommendations, blockers and residual risks. No source changes.