import tempfile
import unittest
from pathlib import Path

from app.skill_cadence import SkillCadenceEngine


class SkillCadenceEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.audit = Path(self.tmp.name) / "cadence.jsonl"
        self.engine = SkillCadenceEngine(audit_path=self.audit)

    def tearDown(self):
        self.tmp.cleanup()

    def test_discover_contains_known_skills(self):
        discovered = self.engine.discover()
        self.assertIn("autohedge-agent-analysis", discovered)
        self.assertIn("freqtrade-backtest-research", discovered)
        self.assertIn("candlestick", discovered)

    def test_validate_all_passes_current_tree(self):
        result = self.engine.validate_all()
        self.assertEqual(result["catalog_issues"], [])
        self.assertEqual(result["reference_issues"], [])
        self.assertTrue(result["passed"])

    def test_metadata_validation(self):
        result = self.engine.metadata_validation()
        self.assertTrue(result["passed"])
        self.assertEqual(result["issues"], [])

    def test_compatibility_testing(self):
        result = self.engine.compatibility_testing()
        self.assertEqual(result["failures"], [])
        self.assertGreaterEqual(result["tested"], 325)

    def test_security_checks_flag_sensitive_keywords(self):
        result = self.engine.security_checks()
        self.assertFalse(result["passed"])
        self.assertTrue(result["findings"])
        for finding in result["findings"][:5]:
            self.assertIn("skill", finding)
            self.assertIn("keyword", finding)

    def test_generate_experimental_candidates_from_signals(self):
        drift_reports = {
            "BTCUSDT": {"signal_drift": True, "current": {"label": "TREND_UP"}, "baseline": {"label": "MIXED"}},
            "ETHUSDT": {"signal_drift": False},
        }
        shadow_reports = {"BTCUSDT": {"eligible_for_review": True}}
        candidates = self.engine.generate_experimental_candidates(drift_reports, shadow_reports, limit=4)
        self.assertTrue(candidates)
        for candidate in candidates:
            self.assertTrue(candidate.id.startswith("autohedge-"))
            self.assertTrue(candidate.human_required)
            self.assertEqual(candidate.version, "0.1.0")

    def test_quality_scores_present(self):
        scores = self.engine.quality_scores()
        self.assertGreaterEqual(scores.get("autohedge-agent-analysis", 0), 0)

    def test_approve_candidate_records_event(self):
        proposals = self.engine.generate_proposals(
            {"BTCUSDT": {"signal_drift": True, "current": {"label": "TREND_UP"}, "baseline": {"label": "MIXED"}}},
            limit=2,
        )
        candidate = proposals[0] if proposals else None
        if not candidate:
            self.skipTest("no candidates generated")
        with self.assertRaises(ValueError):
            self.engine.approve_candidate(candidate, "operator", "viewer")
        result = self.engine.approve_candidate(candidate, "operator", "operator")
        self.assertEqual(result["status"], "approved")
        self.assertIn(candidate.id, self.engine.candidates_by_id())

    def test_version_history_shape(self):
        history = self.engine.version_history()
        self.assertTrue(history)
        self.assertIn("autohedge-agent-analysis", history)


if __name__ == "__main__":
    unittest.main()
