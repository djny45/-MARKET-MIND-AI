# Skill-promotion proposals with human approval gates

`backend/app/skill_promotion.py` implements the skill-promotion phase of the
research-loop engine. Promotion is **never automatic**.

## Model

Each skill has a status:

- `reference_only` — vendored source material (e.g. the 89 Vibe skills)
- `production_ready` — allowlisted and loadable in the catalog
- `experimental` — promote candidate
- `retired` — withdrawn

The engine scores skills from auditable signals and generates proposals. A
proposal changes a skill from `reference_only` to `production_ready` only after
explicit reviewer approval; the engine itself only records decisions and facts.

## Signals

Quality is a base score from:

- catalog presence and loadability
- worker references (`skill_refs` in the registry)
- integrity findings (missing files, duplicate IDs, unresolved references)

Priority is higher for skills with several worker references and no issues.

## API

```python
from app.skill_promotion import PromotionEngine, compatibility_report, promotion_status_summary

engine = PromotionEngine()
scores = engine.score_all()                       # highest scores first
proposals = engine.generate_top_proposals(limit=10)
engine.approve(proposal.id, "operator-name", role="operator")
engine.rollback(proposal.id, "operator-name", reason="regression")
report = compatibility_report()
```

## Boundaries

- Applies only to reference material; research and engineering skills stay
  outside promotion review.
- Approvals require a reviewer in `operator` or `admin` role; the engine cannot
  escalate or override role checks.
- All decisions are appended to the append-only audit log
  (`data/skill_promotion_audit.jsonl`) with timestamps and rationales.
- This module is research-only; it does not modify imported skill files or the
  live catalog. Promotion of reference material that is executable should remain
  under code review, not this engine alone.

Covered by 4 tests in `backend/tests/test_skill_promotion.py`.
