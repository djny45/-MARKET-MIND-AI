import os
import tempfile
import unittest
from unittest.mock import patch

from app.worker_memory import append_memory, read_memory, recall_memory


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
