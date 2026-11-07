import os
import tempfile
import unittest
from unittest.mock import patch

from app import worker_memory
from app.learning_feedback import evaluate_learning_feedback


class LearningFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "feedback.sqlite")
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _candidate(self, worker_id, metrics, topic="RSI historical evaluation"):
        return worker_memory.append_memory(
            worker_id,
            "validation_result",
            {
                "record_type": "research_quality_learning_candidate",
                "topic": topic,
                "metrics": metrics,
            },
            ["research_task:feedback-fixture"],
            "partial",
        )

    def test_feedback_compares_only_latest_approved_candidates(self):
        pending = self._candidate("worker_001", {"claim_reference_coverage": 0.8})
        approved = self._candidate("worker_001", {
            "claim_reference_coverage": 0.8,
            "unknown_source_id_count": 2,
        })
        rejected = self._candidate("worker_001", {"claim_reference_coverage": 0.7})
        worker_memory.review_learning_candidate("worker_001", approved["memory_id"], "approved", "reviewer")
        worker_memory.review_learning_candidate("worker_001", rejected["memory_id"], "rejected", "reviewer")

        result = evaluate_learning_feedback("worker_001", {
            "claim_reference_coverage": 0.95,
            "unknown_source_id_count": 2,
        })
        self.assertEqual(result["status"], "review_required_differences_detected")
        self.assertEqual(result["approved_candidates_compared"], 1)
        self.assertEqual(result["changed_metric_comparisons"], 1)
        self.assertEqual(result["comparisons"][0]["candidate_memory_id"], approved["memory_id"])
        self.assertEqual(result["comparisons"][0]["comparisons"][0]["status"], "changed")
        self.assertNotIn(pending["memory_id"], [x["candidate_memory_id"] for x in result["comparisons"]])
        self.assertNotIn(rejected["memory_id"], [x["candidate_memory_id"] for x in result["comparisons"]])

    def test_feedback_marks_old_approved_reference_as_stale(self):
        candidate = self._candidate("worker_001", {"sample_count": 10})
        worker_memory.review_learning_candidate("worker_001", candidate["memory_id"], "approved", "reviewer")
        with worker_memory._connect() as db:
            db.execute(
                "UPDATE worker_memory SET created_at=? WHERE memory_id=?",
                ("2020-01-01T00:00:00+00:00", candidate["memory_id"]),
            )
        result = evaluate_learning_feedback("worker_001", {"sample_count": 10}, stale_after_days=30)
        self.assertEqual(result["status"], "no_material_metric_differences")
        self.assertTrue(result["comparisons"][0]["stale_reference"])

    def test_latest_review_decision_controls_eligibility(self):
        candidate = self._candidate("worker_001", {"sample_count": 10})
        worker_memory.review_learning_candidate("worker_001", candidate["memory_id"], "approved", "reviewer-a")
        worker_memory.review_learning_candidate("worker_001", candidate["memory_id"], "rejected", "reviewer-b")
        result = evaluate_learning_feedback("worker_001", {"sample_count": 99})
        self.assertEqual(result["status"], "no_comparable_approved_evidence")

    def test_feedback_reports_no_comparable_evidence(self):
        candidate = self._candidate("worker_001", {"sample_count": 10})
        result = evaluate_learning_feedback("worker_001", {"other_metric": 1})
        self.assertEqual(result["status"], "no_comparable_approved_evidence")
        self.assertEqual(result["approved_candidates_compared"], 0)

    def test_feedback_validates_worker_metrics_and_thresholds(self):
        with self.assertRaises(ValueError):
            evaluate_learning_feedback("worker_999", {"sample_count": 1})
        with self.assertRaises(ValueError):
            evaluate_learning_feedback("worker_001", {})
        with self.assertRaises(ValueError):
            evaluate_learning_feedback("worker_001", {"sample_count": float("nan")})
        with self.assertRaises(ValueError):
            evaluate_learning_feedback("worker_001", {"sample_count": 10 ** 1000})
        with self.assertRaises(ValueError):
            evaluate_learning_feedback("worker_001", {"sample_count": 1}, stale_after_days=0)
        with self.assertRaises(ValueError):
            evaluate_learning_feedback("worker_001", {"sample_count": 1}, tolerance=float("inf"))


if __name__ == "__main__":
    unittest.main()
