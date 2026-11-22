# Continuous skill-generation and validation cadence

`backend/app/skill_cadence.py` implements Phase 5: discovery, generation,
validation, security review, and human approval for new skill capabilities.
All capabilities remain research-only; nothing is auto-promoted or installed.

## Discover

`engine.discover()` returns every known skill id from the catalog, the
reference skills, and already-proposed candidates.

## Generate

`engine.generate_experimental_candidates(drift_reports, shadow_reports, limit=8)`
produces `SkillCandidate` records from evidence signals (drift reports and
shadow reports). Each candidate records a rationale, domain and human-required
flag.

## Validate

- `validate_all()` — catalog/reference audit and compatibility.
- `metadata_validation()` — frontmatter checks for non-catalog skill files.
- `compatibility_testing()` — every catalog skill loads with non-empty content.
- `security_checks()` — scan skill text for executable/sensitive keywords.

## Approve

`engine.generate_proposals()` registers pending proposals.
`engine.approve_candidate(candidate, reviewer, role)` appends an audit record
and requires `operator` or `admin`.

## Version management

`version_history()` reports version timelines. Candidate versions start at
`0.1.0` and become `1.0.0` when the skill enters the catalog.

Covered by 9 tests in `backend/tests/test_skill_cadence.py`.
