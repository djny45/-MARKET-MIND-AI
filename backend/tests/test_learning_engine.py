import os
import tempfile
import unittest
from unittest.mock import patch

from app.learning_engine import agent_learning_summary, learning_overview, run_feedback_improvement_cycle
from app.worker_memory import append_memory


class LearningEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "learning.sqlite")
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_feedback_score_excludes_unverified_and_proposals_are_counted(self):
        append_memory("worker_001", "validation_result",
                      {"outcome": "helpful", "summary": "Useful", "metrics": {}},
                      quality_status="unverified")
        append_memory("worker_001", "validation_result",
                      {"outcome": "not_helpful", "summary": "Needs work", "metrics": {}},
                      quality_status="unverified")
        append_memory("worker_001", "validation_result",
                      {"outcome": "unverified", "summary": "Not checked", "metrics": {}},
                      quality_status="unverified")
        append_memory("worker_001", "method_note",
                      {"update_proposal": {"title": "Add source validation"}})
        result = agent_learning_summary("worker_001")
        self.assertEqual(result["feedback_count"], 3)
        self.assertEqual(result["scored_feedback_count"], 2)
        self.assertEqual(result["observed_feedback_score"], 0.5)
        self.assertEqual(result["improvement_proposals"], 1)
        self.assertFalse(result["model_training"])
        self.assertFalse(result["auto_apply"])

    def test_overview_covers_registered_agents_and_discloses_no_training(self):
        result = learning_overview()
        self.assertEqual(result["agent_count"], 550)
        self.assertEqual(len(result["agents"]), 550)
        self.assertFalse(result["autonomous_model_training"])
        self.assertFalse(result["automatic_agent_updates"])
        self.assertIsNone(result["system_feedback_score"])

    def test_feedback_cycle_waits_for_minimum_sample(self):
        result = run_feedback_improvement_cycle("worker_001")
        self.assertEqual(result["cycle_status"], "insufficient_feedback")
        self.assertFalse(result["proposal_created"])
        self.assertFalse(result["model_training"])

    def test_feedback_cycle_creates_review_only_proposal_and_is_idempotent(self):
        for i in range(5):
            append_memory("worker_001", "validation_result",
                          {"outcome": "not_helpful", "summary": f"Missing source context {i}"},
                          quality_status="unverified")
        first = run_feedback_improvement_cycle("worker_001")
        self.assertEqual(first["cycle_status"], "proposal_created_pending_review")
        self.assertTrue(first["proposal_created"])
        self.assertFalse(first["model_training"])
        self.assertFalse(first["auto_apply"])
        second = run_feedback_improvement_cycle("worker_001")
        self.assertEqual(second["cycle_status"], "proposal_already_exists")
        self.assertFalse(second["proposal_created"])

    def test_invalid_limit_is_rejected(self):
        for limit in (0, 201, True):
            with self.assertRaises(ValueError):
                learning_overview(limit)


if __name__ == "__main__":
    unittest.main()
