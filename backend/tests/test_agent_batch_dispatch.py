import os
import tempfile
import unittest
from unittest.mock import patch

from app.agent_council import run_agent_batch


class AgentBatchDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "batch.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_batch_records_explicit_provider_unavailable_for_each_agent(self):
        result = run_agent_batch(["worker_001", "worker_021"], "Analyze provided data", {"x": 1})
        self.assertEqual(result["agent_count_requested"], 2)
        self.assertEqual(result["agent_count_accepted"], 2)
        self.assertEqual(result["status_counts"]["completed"], 2)
        self.assertEqual(result["execution_mode"], "bounded_sequential_shared_provider")
        self.assertFalse(result["paper_trading"])
        self.assertFalse(result["broker_execution"])

    def test_batch_rejects_duplicate_ids(self):
        with self.assertRaises(ValueError):
            run_agent_batch(["worker_001", "worker_001"], "brief")

    def test_batch_rejects_more_than_550_agents(self):
        with self.assertRaises(ValueError):
            run_agent_batch(["worker_001"] * 551, "brief")


if __name__ == "__main__":
    unittest.main()
