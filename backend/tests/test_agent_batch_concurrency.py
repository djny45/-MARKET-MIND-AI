import os
import tempfile
import unittest
from unittest.mock import patch

from app.agent_council import run_agent_batch


class AgentBatchConcurrencyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "batch-concurrent.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_concurrent_batch_keeps_input_order_and_is_bounded(self):
        result = run_agent_batch(
            ["worker_001", "worker_021", "worker_031"],
            "Review supplied evidence",
            {"sample": [1, 2]},
            max_concurrency=2,
        )
        self.assertEqual([item["agent_id"] for item in result["results"]],
                         ["worker_001", "worker_021", "worker_031"])
        self.assertEqual(result["max_concurrency"], 2)
        self.assertEqual(result["execution_mode"], "bounded_concurrent_shared_provider")
        self.assertEqual(result["agent_count_requested"], 3)
        self.assertFalse(result["paper_trading"])
        self.assertFalse(result["broker_execution"])

    def test_rejects_invalid_concurrency(self):
        with self.assertRaises(ValueError):
            run_agent_batch(["worker_001"], "brief", max_concurrency=0)
        with self.assertRaises(ValueError):
            run_agent_batch(["worker_001"], "brief", max_concurrency=17)

    def test_invalid_agent_does_not_cancel_valid_sibling(self):
        result = run_agent_batch(["worker_001", "worker_9999"], "brief", max_concurrency=2)
        self.assertEqual(len(result["results"]), 2)
        self.assertIn(result["results"][1]["status"], {"rejected", "failed"})


if __name__ == "__main__":
    unittest.main()
