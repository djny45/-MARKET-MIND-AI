import os
import tempfile
import unittest
from unittest.mock import patch

from app.worker_memory import append_memory, review_improvement_proposal
from app.staging_experiments import create_staging_experiment, list_staging_experiments


class StagingExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "staging.sqlite")})
        self.env.start()
        self.proposal = append_memory("worker_001", "method_note", {
            "update_proposal": {"title": "Improve source timestamp handling"}
        })

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _payload(self):
        return {"benchmark_id": "fixture-bench-01", "reviewer": "human-reviewer",
                "baseline_metrics": {"coverage": 0.7, "traceability": 0.8},
                "candidate_metrics": {"coverage": 0.75, "traceability": 0.8},
                "notes": "Metrics supplied from isolated fixture run"}

    def test_staging_experiment_requires_latest_approval(self):
        with self.assertRaisesRegex(ValueError, "approved_for_staging"):
            create_staging_experiment("worker_001", self.proposal["memory_id"], self._payload())
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        saved = create_staging_experiment("worker_001", self.proposal["memory_id"], self._payload())
        self.assertEqual(saved["content"]["record_type"], "staging_experiment_result")
        self.assertEqual(saved["content"]["outcome"], "inconclusive")
        self.assertEqual(saved["content"]["execution_mode"], "reviewer_supplied_metrics_only")
        self.assertEqual(list_staging_experiments("worker_001")["count"], 1)

    def test_latest_review_revokes_staging_permission(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer-a")
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "needs_revision", "reviewer-b")
        with self.assertRaisesRegex(ValueError, "latest review status"):
            create_staging_experiment("worker_001", self.proposal["memory_id"], self._payload())

    def test_rejects_wrong_worker_and_malformed_metrics(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        with self.assertRaises(ValueError):
            create_staging_experiment("worker_002", self.proposal["memory_id"], self._payload())
        bad = self._payload()
        bad["candidate_metrics"] = {"coverage": float("nan")}
        with self.assertRaisesRegex(ValueError, "finite"):
            create_staging_experiment("worker_001", self.proposal["memory_id"], bad)

    def test_identical_metrics_are_no_material_change(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        payload = self._payload()
        payload["candidate_metrics"] = dict(payload["baseline_metrics"])
        result = create_staging_experiment("worker_001", self.proposal["memory_id"], payload)
        self.assertEqual(result["content"]["outcome"], "no_material_change")


if __name__ == "__main__":
    unittest.main()
