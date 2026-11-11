import os
import tempfile
import unittest
from unittest.mock import patch

from app.worker_memory import append_memory, read_memory, recall_memory, review_learning_candidate, list_learning_candidates, recall_approved_learning_candidates, review_improvement_proposal, list_improvement_proposals


class WorkerMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "worker-memory.sqlite")
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_memory_is_scoped_and_round_trips_with_provenance(self):
        saved = append_memory(
            "worker_001", "observation",
            {"summary": "SMA calculated from imported history", "count": 42},
            ["historical-import:batch-7"], "partial",
        )
        result = read_memory("worker_001")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memory"][0]["memory_id"], saved["memory_id"])
        self.assertEqual(result["memory"][0]["source_refs"], ["historical-import:batch-7"])
        self.assertEqual(result["memory"][0]["quality_status"], "partial")
        self.assertEqual(read_memory("worker_002")["count"], 0)

    def test_memory_type_filter_and_limit(self):
        append_memory("worker_001", "observation", {"n": 1})
        append_memory("worker_001", "open_question", {"question": "source freshness?"})
        result = read_memory("worker_001", "open_question", 10)
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["memory"][0]["memory_type"], "open_question")

    def test_recall_memory_ranks_relevant_notes_and_keeps_provenance(self):
        unrelated = append_memory(
            "worker_001", "observation",
            {"summary": "weather station temperature calibration"},
            ["weather-log"], "unverified",
        )
        relevant = append_memory(
            "worker_001", "validation_result",
            {"summary": "RSI indicator test passed on historical market bars"},
            ["test-run:rsi-2026"], "partial",
        )
        append_memory(
            "worker_002", "observation",
            {"summary": "RSI historical market analysis from another worker"},
            ["other-worker"], "unverified",
        )
        result = recall_memory("worker_001", "RSI historical market indicator", limit=5)
        self.assertEqual(result["retrieval_mode"], "lexical_keyword_overlap")
        self.assertGreaterEqual(result["count"], 1)
        self.assertEqual(result["memory"][0]["memory_id"], relevant["memory_id"])
        self.assertEqual(result["memory"][0]["source_refs"], ["test-run:rsi-2026"])
        self.assertNotEqual(result["memory"][0]["memory_id"], unrelated["memory_id"])
        self.assertTrue(all(item["worker_id"] == "worker_001" for item in read_memory("worker_001")["memory"]))

    def test_recall_memory_validates_query_and_limit(self):
        with self.assertRaises(ValueError):
            recall_memory("worker_001", "")
        with self.assertRaises(ValueError):
            recall_memory("worker_001", "RSI", limit=0)


    def test_candidate_review_is_append_only_and_worker_scoped(self):
        candidate = append_memory(
            "worker_001", "validation_result",
            {"record_type": "research_quality_learning_candidate", "task_id": "task-1",
             "metrics": {"coverage": 0.8}, "review_required": True},
            ["research_task:task-1"], "partial",
        )
        review = review_learning_candidate(
            "worker_001", candidate["memory_id"], "approved", "operator", "Reviewed metrics only"
        )
        self.assertEqual(review["content"]["decision"], "approved")
        self.assertEqual(review["content"]["candidate_memory_id"], candidate["memory_id"])
        records = read_memory("worker_001", "validation_result")["memory"]
        self.assertEqual(len(records), 2)
        original = next(item for item in records if item["memory_id"] == candidate["memory_id"])
        self.assertTrue(original["content"]["review_required"])
        self.assertEqual(review["source_refs"], [f"learning_candidate:{candidate['memory_id']}"])

    def test_candidate_review_rejects_wrong_worker_and_non_candidate(self):
        candidate = append_memory(
            "worker_001", "validation_result",
            {"record_type": "research_quality_learning_candidate"},
        )
        with self.assertRaises(ValueError):
            review_learning_candidate("worker_002", candidate["memory_id"], "approved", "operator")
        ordinary = append_memory("worker_001", "observation", {"note": "not candidate"})
        with self.assertRaises(ValueError):
            review_learning_candidate("worker_001", ordinary["memory_id"], "approved", "operator")
        with self.assertRaises(ValueError):
            review_learning_candidate("worker_001", candidate["memory_id"], "promote", "operator")


    def test_candidate_listing_exposes_latest_review_and_history(self):
        candidate = append_memory(
            "worker_001", "validation_result",
            {"record_type": "research_quality_learning_candidate", "task_id": "task-list"},
            ["research_task:task-list"], "partial",
        )
        review_learning_candidate("worker_001", candidate["memory_id"], "needs_revision", "reviewer-a", "Need clearer metrics")
        review_learning_candidate("worker_001", candidate["memory_id"], "approved", "reviewer-b", "Rechecked")
        listing = list_learning_candidates("worker_001")
        self.assertEqual(listing["count"], 1)
        item = listing["candidates"][0]
        self.assertEqual(item["memory_id"], candidate["memory_id"])
        self.assertEqual(item["review_status"], "approved")
        self.assertEqual(len(item["review_history"]), 2)
        self.assertEqual(item["latest_review"]["reviewer"], "reviewer-b")

    def test_candidate_listing_validates_worker_and_limit(self):
        with self.assertRaises(ValueError):
            list_learning_candidates("worker_999")
        with self.assertRaises(ValueError):
            list_learning_candidates("worker_001", limit=0)


    def test_approved_candidate_recall_excludes_pending_and_rejected(self):
        pending = append_memory(
            "worker_001", "validation_result",
            {"record_type": "research_quality_learning_candidate", "topic": "RSI indicator calibration"},
            ["research_task:rsi-pending"], "partial",
        )
        rejected = append_memory(
            "worker_001", "validation_result",
            {"record_type": "research_quality_learning_candidate", "topic": "RSI signal threshold"},
            ["research_task:rsi-rejected"], "partial",
        )
        approved = append_memory(
            "worker_001", "validation_result",
            {"record_type": "research_quality_learning_candidate", "topic": "RSI indicator historical validation"},
            ["research_task:rsi-approved"], "partial",
        )
        review_learning_candidate("worker_001", rejected["memory_id"], "rejected", "reviewer")
        review_learning_candidate("worker_001", approved["memory_id"], "approved", "reviewer")
        result = recall_approved_learning_candidates("worker_001", "RSI indicator historical")
        self.assertEqual(result["retrieval_mode"], "approved_candidate_lexical_overlap")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["candidates"][0]["memory_id"], approved["memory_id"])
        self.assertNotIn(pending["memory_id"], [item["memory_id"] for item in result["candidates"]])
        self.assertNotIn(rejected["memory_id"], [item["memory_id"] for item in result["candidates"]])

    def test_approved_candidate_recall_validates_query_and_limit(self):
        with self.assertRaises(ValueError):
            recall_approved_learning_candidates("worker_001", "")
        with self.assertRaises(ValueError):
            recall_approved_learning_candidates("worker_001", "RSI", limit=0)


    def test_improvement_proposal_review_is_append_only_and_latest_decision_wins(self):
        proposal = append_memory(
            "worker_001", "method_note",
            {"update_proposal": {"title": "Add timestamp validation", "status": "pending_review"}},
            ["feedback:sample-1"], "unverified",
        )
        first = review_improvement_proposal(
            "worker_001", proposal["memory_id"], "approved_for_staging", "reviewer-a", "Try in isolated tests",
        )
        second = review_improvement_proposal(
            "worker_001", proposal["memory_id"], "needs_revision", "reviewer-b", "Add a rollback test",
        )
        listing = list_improvement_proposals("worker_001")
        item = listing["proposals"][0]
        self.assertEqual(item["memory_id"], proposal["memory_id"])
        self.assertEqual(item["review_status"], "needs_revision")
        self.assertEqual(len(item["review_history"]), 2)
        self.assertEqual(item["latest_review"]["memory_id"], second["memory_id"])
        self.assertEqual(read_memory("worker_001", "method_note")["count"], 3)
        self.assertEqual(first["content"]["review_boundary"],
                         "staging_review_only_no_code_change_no_deployment_no_model_training")

    def test_improvement_proposal_review_rejects_wrong_worker_and_nonproposal(self):
        proposal = append_memory(
            "worker_001", "method_note", {"update_proposal": {"title": "Proposal"}}
        )
        ordinary = append_memory("worker_001", "method_note", {"note": "not a proposal"})
        with self.assertRaises(ValueError):
            review_improvement_proposal("worker_002", proposal["memory_id"], "rejected", "reviewer")
        with self.assertRaises(ValueError):
            review_improvement_proposal("worker_001", ordinary["memory_id"], "rejected", "reviewer")
        with self.assertRaises(ValueError):
            review_improvement_proposal("worker_001", proposal["memory_id"], "approved", "reviewer")
        with self.assertRaises(ValueError):
            list_improvement_proposals("worker_999")

    def test_worker_id_validation_rejects_non_string_and_blank_values(self):
        invalid_ids = [None, [], {}, 1, "", "   "]
        operations = [
            lambda worker_id: append_memory(worker_id, "observation", {"note": "x"}),
            lambda worker_id: read_memory(worker_id),
            lambda worker_id: recall_memory(worker_id, "RSI"),
            lambda worker_id: list_learning_candidates(worker_id),
            lambda worker_id: list_improvement_proposals(worker_id),
        ]
        for worker_id in invalid_ids:
            for operation in operations:
                with self.subTest(worker_id=worker_id, operation=operation):
                    with self.assertRaises(ValueError):
                        operation(worker_id)

    def test_rejects_unknown_worker_and_invalid_memory_type(self):
        with self.assertRaises(ValueError):
            append_memory("worker_9999", "observation", {})
        with self.assertRaises(ValueError):
            append_memory("worker_001", "system_prompt", {})

    def test_rejects_non_json_or_oversized_content(self):
        with self.assertRaises(ValueError):
            append_memory("worker_001", "observation", {"bad": float("nan")})
        with self.assertRaises(ValueError):
            append_memory("worker_001", "observation", {"text": "x" * 12001})

    def test_rejects_invalid_provenance_and_query_limits(self):
        with self.assertRaises(ValueError):
            append_memory("worker_001", "observation", {}, [""])
        with self.assertRaises(ValueError):
            read_memory("worker_001", limit=0)


if __name__ == "__main__":
    unittest.main()
