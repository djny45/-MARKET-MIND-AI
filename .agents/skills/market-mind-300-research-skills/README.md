# 300 Research Skills — Integration Guide

This catalog contains 300 research skill definitions for the existing 550-worker registry. It does not create 300 models or independently running agents.

## Skill IDs

Use stable IDs `mm-skill-001` through `mm-skill-300`, corresponding to the numbered headings in `SKILL.md`. Keep the catalog version at `1.0.0` until its contents change.

## Recommended integration

1. Generate a versioned manifest from the skill headings.
2. Verify there are 300 unique IDs and titles.
3. Assign only relevant skill IDs to each worker profile.
4. Retrieve selected skill sections on demand; do not inject the full catalog into every worker prompt.
5. Treat skill text as advisory research guidance, never as executable code or privileged instructions.
6. Keep skills separate from permissions, provider access, and secrets.
7. Add handler tests, provenance checks, and human review before enabling a skill.
8. Record the skill IDs and catalog version used for each research task.

## Suggested future API (not implemented)

- `GET /api/skills` — list skill metadata.
- `GET /api/skills/{skill_id}` — retrieve a skill definition.
- `GET /api/workers/{worker_id}/skills` — inspect assigned skills.
- `POST /api/skills/evaluate` — evaluate skills against offline fixtures.

## Enablement checklist

- Unique skill IDs and titles
- Deterministic manifest generation
- Explainable worker-to-skill mapping
- Context retrieval limited to relevant skills
- Tests and review before enablement
- Data provenance and synthetic-data labels retained
- Research-only boundary preserved; no brokerage or trade execution
