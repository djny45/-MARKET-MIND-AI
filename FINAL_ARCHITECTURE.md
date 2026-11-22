# FINAL ARCHITECTURE — delivered system

This describes what is actually present in the repository, not an aspiration.

## Runtime topology

- **FastAPI backend** (`backend/app/main.py`, 140 routes) — research APIs,
  validation, task queue endpoints, optional bearer auth, rate limiting, CORS
  allowlist, health/readiness.
- **agent-supervisor** — separate Compose service consuming the shared SQLite
  task queue; startup recovery, bounded dispatch, failure classification.
- **Frontend** — React + TypeScript bundled by esbuild (`frontend/scripts/build.mjs`)
  and served by Nginx through the Compose proxy; supports root and project-site
  base paths.
- **Local MCP servers** — `market-mind-ai` (6 read-only research tools) and
  `camofox-browser` (31 interactive browser tools, localhost-only, no credentials).
- **SQLite** on a named Docker volume — research data, task history, memory
  candidates, audit events.

## Multi-agent model

550 worker profiles are **registry templates** with distinct IDs, departments
(20), specialties, memory namespaces, context hashes and skill references. They
share one central intelligence provider; they are not 550 independent models or
always-on processes. Task routing is bounded and deterministic; inference is
optional and disabled by default. Results are aggregated with structural
validation, and all transitions are recorded as audit events.

## Skill system

325 allowlisted skills are discoverable and loadable through `skill_catalog.py`.
300 are generated research procedures from one versioned catalog file; the
remaining 25 are research/engineering playbooks, including 3 AutoHedge skills
and 1 Freqtrade methodology skill. 89 Vibe-Trading skills are vendored as
reference-only text and are deliberately absent from the allowlist. No imported
script is executed.

## Memory and governance

Append-only worker memory with review-gated learning candidates and improvement
proposals; metrics-only validation records; no autonomous model training, prompt
mutation or strategy deployment. Optional deployment-wide bearer auth and
environment validation exist; per-user identity and roles do not.

## Research and simulation boundary

Historical data adapters, evidence/citation auditing, benchmark and promotion
review, and deterministic research skills are present. Market-making, wallet
signing and execution code from imported repositories remains inert reference
material. Health responses report `paper_trading: false` and
`broker_execution: false`. No brokerage integration exists.

## Security boundaries

- No secrets in repository, frontend bundle, diagnostics or reports.
- Browser research: allowlisted read-only fetcher; Camofox bound to loopback
  with no API/access keys, isolated profile, upload and cookie directories.
- Optional rate limiting and CORS origin allowlist; TLS must terminate at an
  operator-controlled ingress before any non-private exposure.
