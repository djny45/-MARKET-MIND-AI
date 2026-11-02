import os
import tempfile
import unittest
from unittest.mock import patch

from app.learning_engine import agent_learning_summary, learning_overview
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

    def test_invalid_limit_is_rejected(self):
        for limit in (0, 201, True):
            with self.assertRaises(ValueError):
                learning_overview(limit)


if __name__ == "__main__":
    unittest.main()
