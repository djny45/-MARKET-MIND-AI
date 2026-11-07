import os
import tempfile
import unittest
from unittest.mock import patch

from app.learning_engine import agent_learning_summary, learning_overview, run_feedback_improvement_cycle, build_feedback_staging_plan
from app.worker_memory import append_memory, review_improvement_proposal


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

    def test_latest_feedback_timestamp_ignores_invalid_and_normalizes_utc(self):
        def fake_read_memory(worker_id, memory_type, limit):
            if memory_type == "validation_result":
                return {"memory": [
                    {"content": {"outcome": "helpful"}, "created_at": "2024-01-01T12:00:00+05:30"},
                    {"content": {"outcome": "not_helpful"}, "created_at": "2024-02-01T00:00:00Z"},
                    {"content": {"outcome": "unverified"}, "created_at": "2025-01-01T00:00:00"},
                    {"content": {"outcome": "helpful"}, "created_at": "not-a-date"},
                ]}
            return {"memory": []}

        with patch("app.learning_engine.read_memory", side_effect=fake_read_memory):
            result = agent_learning_summary("worker_001")

        self.assertEqual(result["latest_feedback_at"], "2024-02-01T00:00:00+00:00")

    def test_feedback_trend_compares_older_and_newer_scored_windows(self):
        outcomes = ["not_helpful", "not_helpful", "partially_helpful",
                    "helpful", "helpful", "helpful"]
        records = [
            {"content": {"outcome": outcome}, "created_at": f"2025-01-{day:02d}T00:00:00+00:00"}
            for day, outcome in enumerate(outcomes, start=1)
        ]
        def fake_read_memory(worker_id, memory_type, limit):
            return {"memory": records if memory_type == "validation_result" else []}
        with patch("app.learning_engine.read_memory", side_effect=fake_read_memory):
            result = agent_learning_summary("worker_001")
        trend = result["feedback_trend"]
        self.assertEqual(trend["status"], "descriptive_trend_available")
        self.assertEqual(trend["older_window_count"], 3)
        self.assertEqual(trend["newer_window_count"], 3)
        self.assertEqual(trend["older_window_score"], 0.1667)
        self.assertEqual(trend["newer_window_score"], 1.0)
        self.assertEqual(trend["score_delta"], 0.8333)

    def test_feedback_trend_requires_minimum_dated_sample(self):
        records = [
            {"content": {"outcome": "helpful"}, "created_at": "2025-01-01T00:00:00+00:00"}
            for _ in range(5)
        ]
        def fake_read_memory(worker_id, memory_type, limit):
            return {"memory": records if memory_type == "validation_result" else []}
        with patch("app.learning_engine.read_memory", side_effect=fake_read_memory):
            result = agent_learning_summary("worker_001")
        self.assertEqual(result["feedback_trend"]["status"], "insufficient_feedback")
        self.assertIsNone(result["feedback_trend"]["score_delta"])

    def test_overview_covers_registered_agents_and_discloses_no_training(self):
        result = learning_overview()
        self.assertEqual(result["agent_count"], 550)
        self.assertEqual(len(result["agents"]), 550)
        self.assertFalse(result["autonomous_model_training"])
        self.assertFalse(result["automatic_agent_updates"])
        self.assertIsNone(result["system_feedback_score"])

    def test_system_feedback_score_is_weighted_by_scored_feedback_count(self):
        fake_agents = [
            {"id": "worker_001"},
            {"id": "worker_002"},
        ]
        summaries = [
            {"feedback_count": 10, "scored_feedback_count": 10,
             "improvement_proposals": 0, "observed_feedback_score": 1.0},
            {"feedback_count": 1, "scored_feedback_count": 1,
             "improvement_proposals": 0, "observed_feedback_score": 0.0},
        ]
        with patch("app.learning_engine.list_workers", return_value=fake_agents), \
             patch("app.learning_engine.agent_learning_summary", side_effect=summaries):
            result = learning_overview()

        self.assertEqual(result["system_feedback_score"], 0.9091)
        self.assertEqual(result["scored_feedback_records"], 11)

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



    def test_feedback_cycle_aggregates_issue_categories_into_targeted_proposal(self):
        categories = [
            "data_provenance", "data_provenance", "data_provenance",
            "missing_data", "data_provenance",
        ]
        for index, category in enumerate(categories):
            append_memory(
                "worker_001", "validation_result",
                {
                    "outcome": "not_helpful" if index < 4 else "partially_helpful",
                    "summary": f"Feedback example {index}: improve evidence checks",
                    "issue_category": category,
                },
                source_refs=[f"feedback:category-{index}"],
                quality_status="unverified",
            )

        result = run_feedback_improvement_cycle("worker_001")
        self.assertEqual(result["cycle_status"], "proposal_created_pending_review")
        proposal = result["proposal"]
        self.assertEqual(proposal["dominant_issue_category"], "data_provenance")
        self.assertEqual(proposal["issue_category_counts"]["data_provenance"], 4)
        self.assertEqual(proposal["issue_category_counts"]["missing_data"], 1)
        self.assertEqual(proposal["weak_or_partial_feedback_count"], 5)
        self.assertIn("source identity", proposal["proposed_change"])
        self.assertEqual(len(proposal["evidence_refs"]), 5)
        self.assertFalse(proposal["auto_apply"])
        self.assertFalse(result["model_training"])

    def test_unknown_feedback_issue_category_is_grouped_as_other(self):
        for index in range(5):
            append_memory(
                "worker_001", "validation_result",
                {
                    "outcome": "not_helpful",
                    "summary": f"Unclassified reviewer note {index}",
                    "issue_category": "free-form-untrusted-category",
                },
                source_refs=[f"feedback:unknown-category-{index}"],
                quality_status="unverified",
            )
        result = run_feedback_improvement_cycle("worker_001")
        self.assertEqual(result["proposal"]["dominant_issue_category"], "other")
        self.assertEqual(result["proposal"]["issue_category_counts"], {"other": 5})
        self.assertIn("held-out feedback", result["proposal"]["proposed_change"])


    def test_feedback_staging_plan_requires_latest_review_approval(self):
        for index in range(5):
            append_memory(
                "worker_001", "validation_result",
                {"outcome": "not_helpful", "summary": f"Provenance gap {index}",
                 "issue_category": "data_provenance"},
                quality_status="unverified",
            )
        result = run_feedback_improvement_cycle("worker_001")
        proposal_id = result["proposal_memory_id"]

        with self.assertRaisesRegex(ValueError, "approved_for_staging"):
            build_feedback_staging_plan("worker_001", proposal_id)

        review_improvement_proposal(
            "worker_001", proposal_id, "approved_for_staging", "reviewer",
            "Approve isolated fixture evaluation only",
        )
        plan = build_feedback_staging_plan("worker_001", proposal_id)
        self.assertEqual(plan["issue_category"], "data_provenance")
        self.assertEqual(plan["review_status"], "approved_for_staging")
        self.assertEqual(plan["experiment_design"]["minimum_repeat_runs"], 3)
        self.assertTrue(plan["promotion_gate"]["requires_human_decision"])
        self.assertFalse(plan["promotion_gate"]["auto_promote"])
        self.assertFalse(plan["promotion_gate"]["model_training"])
        self.assertIn("/staging-benchmark", plan["next_api_endpoint"])

    def test_feedback_staging_plan_rejects_unknown_proposal(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            build_feedback_staging_plan("worker_001", "missing-proposal-id")

if __name__ == "__main__":
    unittest.main()
