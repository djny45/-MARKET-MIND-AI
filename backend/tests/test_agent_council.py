import os
import tempfile
import unittest
from unittest.mock import patch

from app.agent_council import run_agent_council


class AgentCouncilTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "council.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_council_uses_distinct_agent_contexts_and_shared_core(self):
        result = run_agent_council(["worker_001", "worker_021"], "Compare supplied metrics", {"a": 1})
        self.assertEqual(result["agent_count_requested"], 2)
        self.assertEqual(result["agent_count_with_analysis"], 0)
        self.assertEqual(result["shared_core"], "shared_central_intelligence")
        self.assertEqual(result["synthesis_status"], "provider_unavailable_or_not_configured")
        self.assertNotEqual(result["members"][0]["brain_context_sha256"], result["members"][1]["brain_context_sha256"])
        self.assertIsNone(result["consensus"])

    def test_council_rejects_duplicate_or_unknown_agents(self):
        with self.assertRaises(ValueError):
            run_agent_council(["worker_001", "worker_001"], "Brief")
        with self.assertRaises(ValueError):
            run_agent_council(["worker_9999"], "Brief")

    def test_council_bounds_member_count_and_input(self):
        with self.assertRaises(ValueError):
            run_agent_council([], "Brief")
        with self.assertRaises(ValueError):
            run_agent_council(["worker_001"] * 9, "Brief")
        with self.assertRaises(ValueError):
            run_agent_council(["worker_001"], "x" * 4001)


if __name__ == "__main__":
    unittest.main()
