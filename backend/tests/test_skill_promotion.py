import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.skill_integrity import audit_reference_skills
from app.skill_promotion import (
    PromotionEngine,
    compatibility_report,
    get_skill_version,
    promotion_status_summary,
)


class PromotionEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = Path(self.tmp.name) / "promo.jsonl"
        with patch("app.skill_promotion.PROMOTION_AUDIT_LOG", self.audit):
            self.engine = PromotionEngine()
        self.reference_id = audit_reference_skills()["entries"][0]["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def test_scores_report_statuses(self):
        self.assertEqual(self.engine.score_skill("autohedge-agent-analysis").status, "production_ready")
        self.assertIn(self.engine.score_skill(self.reference_id).status, ("reference_only", "retired"))
        scores = {score.skill_id: score for score in self.engine.score_all()}
        self.assertIn("autohedge-agent-analysis", scores)
        self.assertIn(self.reference_id, scores)

    def test_generate_top_proposals(self):
        proposals = self.engine.generate_top_proposals(limit=5)
        self.assertTrue(proposals)
        for proposal in proposals:
            self.assertEqual(proposal.status, "pending_review")
            self.assertTrue(proposal.id.startswith("promo-"))
            self.assertEqual(proposal.current_status, "reference_only")
            self.assertEqual(proposal.target_status, "production_ready")
        proposal = self.engine.generate_proposal(self.reference_id)
        self.assertIn(proposal.skill_id, {p.skill_id for p in proposals + [proposal]})
        self.assertEqual(proposal.current_status, "reference_only")

    def test_proposal_lifecycle_requires_review_approval(self):
        proposals = self.engine.generate_top_proposals(limit=1)
        if not proposals:
            self.skipTest("no reference candidates available")
        proposal = proposals[0]
        approved = self.engine.approve(proposal.id, "operator-1", "operator")
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.reviewer, "operator-1")
        with self.assertRaises(ValueError):
            self.engine.approve(proposal.id, "operator-2", "operator")
        rolled = self.engine.rollback(proposal.id, "operator-1", "regression")
        self.assertEqual(rolled.status, "rejected")
        with self.assertRaises(ValueError):
            self.engine.rollback(proposal.id, "operator-1", "again")

    def test_approve_rejects_non_reviewer_roles(self):
        proposals = self.engine.generate_top_proposals(limit=1)
        for role in ("viewer", "analyst"):
            with self.assertRaises(ValueError):
                self.engine.approve(proposals[0].id, "user", role)

    def test_summary_and_audit_are_consistent(self):
        summary = promotion_status_summary(self.engine)
        self.assertEqual(summary["total"], len(self.engine.list_proposals()))
        record_count = sum(1 for _ in self.audit.open()) if self.audit.is_file() else 0
        self.assertEqual(record_count, summary["total"])

    def test_compatibility_report(self):
        report = compatibility_report()
        self.assertEqual(report["overlap"], [])
        self.assertTrue(report["compatible"])
        self.assertEqual(report["catalog_count"], 325)

    def test_versions(self):
        self.assertEqual(get_skill_version("autohedge-agent-analysis"), "1.0.0")
        self.assertEqual(get_skill_version(self.reference_id, set()), "0.1.0")


if __name__ == "__main__":
    unittest.main()
