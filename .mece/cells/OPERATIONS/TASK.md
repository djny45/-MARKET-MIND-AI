# Cell OPERATIONS — Read-only deployment and recovery audit

Read AGENTS.md and inspect Docker/Compose, Nginx/proxy configuration, backup/restore utilities, health checks, operational docs and logging/monitoring setup.

Do not deploy, start/stop production services, access remote hosts, modify data, or handle credentials.

Assess:
- Intended private deployment topology and exposed ports.
- Persistent volumes, backup integrity, restore safety and recovery procedure.
- Health/readiness semantics and whether they prove data availability (they should not be overstated).
- Logs, metrics, alerting, resource limits and rotation.
- Migration/rollback and incident-response procedures.
- Host-specific validation still required.

Write .mece/cells/OPERATIONS/REPORT.md with inspected paths, evidence, safe checks run, operational risks, prioritized actions, blockers and residual risks. No source changes.