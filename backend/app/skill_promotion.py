"""Skill-promotion proposals with human approval gates (research-only).

Skill quality is scored from auditable signals: catalog presence, SKILL.md
metadata, worker references, and execution of the existing integrity checks.
Promotion is proposed deterministically but applied only after explicit
reviewer approval; this module never grants permissions by itself.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from .skill_integrity import audit_catalog, audit_reference_skills

PROMOTION_AUDIT_LOG = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db")).with_name(
    "skill_promotion_audit.jsonl"
)
PROMOTABLE_STATUSES = ("reference_only", "experimental", "production_ready")
ALLOWED_PROMOTION_ROLES = ("operator", "admin")


@dataclass(frozen=True)
class SkillScore:
    skill_id: str
    status: str
    base_score: int
    factors: dict
    issues: list[str]

    def to_record(self) -> dict:
        return asdict(self)


@dataclass
class PromotionProposal:
    id: str
    skill_id: str
    current_status: str
    target_status: str
    priority: int
    score: int
    reasons: list[str]
    status: str  # pending_review, approved, rejected, superseded
    reviewer: str = ""
    decision: str = ""
    created_at: str = ""
    approved_at: str = ""

    def to_record(self) -> dict:
        return asdict(self)


class PromotionEngine:
    """Scores skills and proposes promotions; approvals are explicit operator acts."""

    def __init__(self, catalog_audit: dict | None = None, reference_audit: dict | None = None):
        self._catalog = catalog_audit or audit_catalog()
        self._reference = reference_audit or audit_reference_skills()
        self._promotion_events: list[PromotionProposal] = []
        self._audit_path = PROMOTION_AUDIT_LOG

    # --- scoring ---------------------------------------------------------
    def score_skill(self, skill_id: str) -> SkillScore:
        catalog_ids = set(self._catalog["ids"])
        reference_ids = {entry["id"] for entry in self._reference["entries"]}
        skill_id = str(skill_id)
        issues: list[str] = []
        if skill_id in catalog_ids:
            status = "production_ready"
            if any(issue["id"] == skill_id for issue in self._catalog["issues"]):
                issues.append("catalog_integrity_issue")
        elif skill_id in reference_ids:
            status = "reference_only"
            if any(issue["id"] == skill_id for issue in self._reference["issues"]):
                issues.append("reference_integrity_issue")
        else:
            status = "retired"

        base_score = 0
        if status == "production_ready":
            base_score = 50
        elif status == "reference_only":
            base_score = 20

        used_by_workers = sum(
            1 for worker in self._used_by_workers()
            if skill_id in (worker.get("skill_refs") or [])
        )
        base_score += min(used_by_workers * 2, 20)

        all_issues = self._catalog["issues"] + self._reference["issues"]
        total_issues = sum(1 for issue in all_issues if issue["id"] == skill_id)
        base_score -= min(total_issues * 5, 15)

        factors = {
            "status": status,
            "used_by_workers": used_by_workers,
            "integrity_issues": total_issues,
            "score": base_score,
        }
        if issues:
            factors["issues"] = issues
        return SkillScore(skill_id, status, base_score, factors, issues)

    def _used_by_workers(self) -> list[dict]:
        from .workers import list_workers
        return list_workers()

    def score_all(self, limit: int | None = None) -> list[SkillScore]:
        candidates = list(self._catalog["ids"]) + [e["id"] for e in self._reference["entries"]]
        scores = sorted(
            (self.score_skill(skill_id) for skill_id in set(candidates)),
            key=lambda score: score.base_score,
            reverse=True,
        )
        return scores if limit is None else scores[:limit]

    # --- proposals -------------------------------------------------------
    def generate_proposal(self, skill_id: str) -> PromotionProposal:
        score = self.score_skill(skill_id)
        if score.status != "reference_only":
            raise ValueError(f"{skill_id} is not a promotion candidate ({score.status})")
        proposal = PromotionProposal(
            id=f"promo-{skill_id}-{len(self._promotion_events) + 1:04d}",
            skill_id=skill_id,
            current_status=score.status,
            target_status="production_ready",
            priority=1 if score.factors["used_by_workers"] >= 2 else 3,
            score=score.base_score,
            reasons=[reason for reason in score.factors.get("issues", []) or ["quality metrics passed"]] + ["requires_review"],
            status="pending_review",
        )
        self._promotion_events.append(proposal)
        self._persist(proposal, "generated")
        return proposal

    def generate_top_proposals(self, limit: int = 10) -> list[PromotionProposal]:
        candidates = [score for score in self.score_all() if score.status == "reference_only"]
        return [self.generate_proposal(score.skill_id) for score in candidates[:limit]]

    def approve(self, proposal_id: str, reviewer: str, role: str) -> PromotionProposal:
        if role not in ALLOWED_PROMOTION_ROLES:
            raise ValueError("role must be an approved promotion reviewer role")
        proposal = next((p for p in self._promotion_events if p.id == proposal_id), None)
        if not proposal or proposal.status != "pending_review":
            raise ValueError(f"{proposal_id} is not pending review")
        decision = PromotionProposal(
            id=proposal_id,
            skill_id=proposal.skill_id,
            current_status=proposal.current_status,
            target_status=proposal.target_status,
            priority=proposal.priority,
            score=proposal.score,
            reasons=proposal.reasons,
            status="approved",
            reviewer=reviewer,
            decision="approved",
            created_at=proposal.created_at or _timestamp(),
            approved_at=_timestamp(),
        )
        self._promotion_events[-1] = decision
        self._persist(decision, "approved")
        return decision

    def reject(self, proposal_id: str, reviewer: str, reason: str) -> PromotionProposal:
        proposal = next((p for p in self._promotion_events if p.id == proposal_id), None)
        if not proposal or proposal.status != "pending_review":
            raise ValueError(f"{proposal_id} is not pending review")
        decision = PromotionProposal(
            id=proposal_id,
            skill_id=proposal.skill_id,
            current_status=proposal.current_status,
            target_status=proposal.target_status,
            priority=proposal.priority,
            score=proposal.score,
            reasons=proposal.reasons + [f"rejected: {reason}"],
            status="rejected",
            reviewer=reviewer,
            decision=reason,
            created_at=proposal.created_at or _timestamp(),
        )
        self._promotion_events[-1] = decision
        self._persist(decision, "rejected")
        return decision

    def rollback(self, proposal_id: str, reviewer: str, reason: str) -> PromotionProposal:
        proposal = next((p for p in self._promotion_events if p.id == proposal_id), None)
        if not proposal or proposal.status != "approved":
            raise ValueError(f"{proposal_id} is not approved and cannot be rolled back")
        decision = PromotionProposal(
            id=proposal_id,
            skill_id=proposal.skill_id,
            current_status=proposal.current_status,
            target_status=proposal.target_status,
            priority=proposal.priority,
            score=proposal.score,
            reasons=proposal.reasons + [f"rollback: {reason}"],
            status="rejected",
            reviewer=reviewer,
            decision=reason,
            created_at=proposal.created_at,
            approved_at=proposal.approved_at,
        )
        self._promotion_events[-1] = decision
        self._persist(decision, "rollback")
        return decision

    def list_proposals(self, status: str | None = None) -> list[PromotionProposal]:
        if status:
            return [p for p in self._promotion_events if p.status == status]
        return self._promotion_events

    def _persist(self, proposal: PromotionProposal, event: str) -> None:
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._audit_path, "a", encoding="utf-8") as handle:
            record = {
                "event": event,
                "timestamp": _timestamp(),
                "proposal": proposal.to_record(),
            }
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def _timestamp() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def read_promotion_audit(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    records = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    return records


def get_skill_version(skill_id: str, catalog_ids: set[str] | None = None) -> str:
    catalog = audit_catalog()
    ids = set(catalog["ids"]) if catalog_ids is None else catalog_ids
    return "1.0.0" if skill_id in ids else "0.1.0"


def compatibility_report(catalog_audit: dict | None = None, reference_audit: dict | None = None) -> dict:
    """Verify version compatibility across catalog and reference inventories."""
    catalog = catalog_audit or audit_catalog()
    reference = reference_audit or audit_reference_skills()
    catalog_ids = set(catalog["ids"])
    reference_ids = {entry["id"] for entry in reference["entries"]}
    overlap = catalog_ids & reference_ids
    return {
        "compatible": not overlap and not catalog["issues"] and not reference["issues"],
        "catalog_count": len(catalog_ids),
        "reference_count": len(reference_ids),
        "overlap": sorted(overlap),
        "catalog_issues": catalog["issues"],
        "reference_issues": reference["issues"],
    }


def promotion_status_summary(engine: PromotionEngine) -> dict:
    proposals = engine.list_proposals()
    return {
        "total": len(proposals),
        "pending_review": len(engine.list_proposals("pending_review")),
        "approved": len(engine.list_proposals("approved")),
        "rejected": len(engine.list_proposals("rejected")),
        "top_candidates": [score.skill_id for score in engine.score_all()[:10] if score.status == "reference_only"],
        "research_only": True,
        "broker_execution": False,
    }
