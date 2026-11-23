"""Continuous skill-generation and validation cadence (research-only).

Discover, generate, validate, score and propose new skills from accumulated
evidence. Security and permission checks gate candidates for human approval;
nothing is auto-promoted or auto-installed.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .skill_integrity import audit_catalog, audit_reference_skills, frontmatter
from .skill_promotion import PromotionEngine, compatibility_report

AUDIT_PATH = Path(os.getenv("MARKET_MIND_DB", "./data/market_mind.db")).with_name(
    "skill_cadence_audit.jsonl"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = REPO_ROOT / ".agents" / "skills"

SENSITIVE_KEYWORDS = frozenset({"execute", "subprocess", "os.system", "wget", "curl", "shell", "browser_use", "playwright", "web3", "eth", "wallet"})


@dataclass(frozen=True)
class SkillCandidate:
    id: str
    name: str
    domain: str
    rationale: str
    version: str
    human_required: bool

    def to_record(self) -> dict:
        return asdict(self)


class SkillCadenceEngine:
    def __init__(self, audit_path: Path | None = None, skills_root: Path | None = None):
        self.audit_path = Path(audit_path) if audit_path else AUDIT_PATH
        self.skills_root = Path(skills_root) if skills_root else SKILLS_ROOT
        self._catalog_audit = audit_catalog()
        self._reference_audit = audit_reference_skills()
        self._promotion = PromotionEngine(self._catalog_audit, self._reference_audit)
        self._events: list[dict] = []
        self._pending_proposals: dict[str, SkillCandidate] = {}

    # --- discovery -------------------------------------------------------
    def discover(self) -> list[str]:
        """All known skill ids from catalog, reference and already-proposed."""
        catalog_ids = set(self._catalog_audit["ids"])
        reference_ids = {entry["id"] for entry in self._reference_audit["entries"]}
        proposed = {proposal.skill_id for proposal in self._promotion.list_proposals()}
        return sorted(catalog_ids | reference_ids | proposed)

    # --- generation ------------------------------------------------------
    def generate_experimental_candidates(
        self,
        drift_reports: dict[str, Any] | None = None,
        shadow_reports: dict[str, Any] | None = None,
        limit: int = 8,
    ) -> list[SkillCandidate]:
        """Generate experimental skill candidates from evidence signals."""
        candidates: list[SkillCandidate] = []
        drift_reports = drift_reports or {}
        shadow_reports = shadow_reports or {}
        if drift_reports:
            for symbol, report in sorted(drift_reports.items())[: limit // 2 + 1]:
                if report.get("signal_drift"):
                    candidates.append(SkillCandidate(
                        id=f"autohedge-regime-{symbol.lower()}",
                        name=f"Regime Detection — {symbol}",
                        domain="Regime / drift analysis",
                        rationale=f"High drift signal for {symbol}: {report['current']['label']} after {report['baseline']['label']}",
                        version="0.1.0",
                        human_required=True,
                    ))
        if shadow_reports:
            for symbol, report in sorted(shadow_reports.items())[: limit // 2 + 1]:
                if report.get("eligible_for_review"):
                    candidates.append(SkillCandidate(
                        id=f"autohedge-shadow-{symbol.lower()}",
                        name=f"Shadow-Shadowed Strategy — {symbol}",
                        domain="Shadow session engineering",
                        rationale=f"Strategy {symbol} passed 24h shadow window with positive PnL and no failed cycles",
                        version="0.1.0",
                        human_required=True,
                    ))
        # Deduplicate against all known ids.
        known = set(self.discover())
        return [c for c in candidates if c.id not in known][:limit]

    # --- validation ------------------------------------------------------
    def validate_all(self) -> dict:
        catalog_issues = self._catalog_audit["issues"]
        reference_issues = self._reference_audit["issues"]
        compatibility = compatibility_report(self._catalog_audit, self._reference_audit)
        return {
            "catalog_skills": self._catalog_audit["count"],
            "reference_skills": self._reference_audit["count"],
            "catalog_issues": catalog_issues,
            "reference_issues": reference_issues,
            "compatible": compatibility["compatible"],
            "overlap": compatibility["overlap"],
            "passed": not catalog_issues and not reference_issues and compatibility["compatible"],
        }

    def metadata_validation(self) -> dict:
        issues: list[dict] = []
        catalog_ids = set(self._catalog_audit["ids"])
        catalog_pack_names = {skill_id for skill_id in catalog_ids if skill_id.startswith("mm-skill-")}
        catalog_pack_names.add("market-mind-300-research-skills")
        skill_files = self._skill_files()
        if not skill_files:
            return {
                "issues": [{"skill": "<none>", "issue": "no_skill_files_scanned"}],
                "scanned": 0,
                "passed": False,
            }
        for name, skill_file in skill_files:
            meta = frontmatter(skill_file.read_text(encoding="utf-8", errors="replace"))
            if name in catalog_ids or name in catalog_pack_names or name.startswith("mm-skill-"):
                # Catalog-backed files are validated by the catalog audit.
                continue
            if not meta.get("name"):
                issues.append({"skill": name, "issue": "missing_name"})
            if not meta.get("description"):
                issues.append({"skill": name, "issue": "missing_description"})
        return {"issues": issues, "scanned": len(skill_files), "passed": not issues}

    def compatibility_testing(self) -> dict:
        from .skill_catalog import load_skill
        failures: list[str] = []
        for skill_id in self._catalog_audit["ids"]:
            try:
                result = load_skill(skill_id)
                if not str(result.get("content", "")).strip():
                    failures.append(f"{skill_id}: empty_content")
            except (KeyError, FileNotFoundError):
                failures.append(f"{skill_id}: not_loadable")
        return {"failures": failures, "passed": not failures, "tested": len(self._catalog_audit["ids"])}

    def security_checks(self) -> dict:
        """Flag executable/sensitive capabilities in imported text for human review.

        Fails closed: when no skill files can be scanned the check reports a
        finding instead of silently passing.
        """
        findings: list[dict] = []
        skill_files = self._skill_files()
        if not skill_files:
            return {
                "findings": [{"skill": "<none>", "keyword": "no_skill_files_scanned"}],
                "scanned": 0,
                "passed": False,
            }
        for name, skill_file in skill_files:
            try:
                text = skill_file.read_text(encoding="utf-8", errors="replace").lower()
            except OSError:
                continue
            for keyword in SENSITIVE_KEYWORDS:
                if keyword.lower() in text:
                    findings.append({"skill": name, "keyword": keyword})
        return {"findings": findings, "scanned": len(skill_files), "passed": not findings}

    def quality_scores(self) -> dict[str, float]:
        scores = {score.skill_id: score.base_score for score in self._promotion.score_all()}
        scores.update({name: 100.0 for name in self._catalog_audit["ids"] if not any(i["id"] == name for i in self._catalog_audit["issues"])})
        return scores

    # --- proposals -------------------------------------------------------
    def generate_proposals(self, *args, **kwargs) -> list[SkillCandidate]:
        candidates = self.generate_experimental_candidates(*args, **kwargs)
        for candidate in candidates:
            self._pending_proposals[candidate.id] = candidate
        return candidates

    def candidates_by_id(self) -> dict[str, dict]:
        return {c.id: c.to_record() for c in self._pending_proposals.values()}

    def approve_candidate(self, candidate: SkillCandidate, reviewer: str, role: str) -> dict:
        if role not in ("operator", "admin"):
            raise ValueError("role must be operator or admin")
        stored = self._pending_proposals.get(candidate.id, candidate)
        self._persist("approved", {**stored.to_record(), "reviewer": reviewer, "role": role})
        return {**stored.to_record(), "status": "approved", "reviewer": reviewer}

    def version_history(self) -> dict[str, list[str]]:
        return {
            skill_id: ["0.1.0"]
            for skill_id in self._catalog_audit["ids"]
        }

    def list_events(self) -> list[dict]:
        return self._events

    def _persist(self, event: str, record: dict) -> None:
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._events.append({"event": event, "record": record})
        with open(self.audit_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, "record": record}, sort_keys=True) + "\n")

    def _skill_files(self):
        root = Path(self.skills_root)
        files = sorted(root.rglob("SKILL.md")) if root.is_dir() else []
        return [(p.parent.name, p) for p in files]
