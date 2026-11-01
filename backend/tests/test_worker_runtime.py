import unittest

from app.worker_runtime import assign_worker, worker_runtime_status


class WorkerRuntimeTests(unittest.TestCase):
    def test_supported_nodes_route_to_shared_core_profiles(self):
        for node_type in ("sma", "rsi", "returns", "volatility", "research_summary"):
            assignment = assign_worker(node_type)
            self.assertTrue(assignment["worker_id"].startswith("worker_"))
            self.assertEqual(assignment["intelligence_core"], "shared_central_intelligence")
            self.assertEqual(assignment["execution_mode"], "deterministic_analytical_handler")

    def test_explicit_worker_must_match_node_department(self):
        with self.assertRaises(ValueError):
            assign_worker("sma", "worker_001")

    def test_unknown_worker_and_node_are_rejected(self):
        with self.assertRaises(ValueError):
            assign_worker("sma", "worker_9999")
        with self.assertRaises(ValueError):
            assign_worker("unknown_node")

    def test_runtime_status_does_not_claim_llm_or_broker_execution(self):
        status = worker_runtime_status()
        self.assertEqual(status["worker_profile_count"], 550)
        self.assertFalse(status["llm_inference_enabled"])
        self.assertFalse(status["broker_execution"])


if __name__ == "__main__":
    unittest.main()
