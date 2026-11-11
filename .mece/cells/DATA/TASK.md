# Cell DATA — Read-only data/provider audit

Read AGENTS.md and the relevant data/research playbooks only. Inspect data adapters, ingestion, storage, symbol mapping, provenance, data-quality checks and documentation.

Do not connect to external paid services, use credentials, scrape websites, alter databases, or implement a provider.

Assess:
- Which data sources are actually configured and reachable from code.
- Synthetic versus historical versus live/delayed data labeling.
- Provenance, timestamps, timezone handling, freshness and missing-data behavior.
- Provider licensing/entitlement/rate-limit requirements and whether these are documented.
- Symbol/venue coverage and known gaps; do not claim completeness.
- Whether derived indicators are computed from valid underlying observations.

Write .mece/cells/DATA/REPORT.md with evidence and paths, actual provider status (not assumptions), safe validation commands/results, prioritized gaps, blockers and residual risks. No source changes.