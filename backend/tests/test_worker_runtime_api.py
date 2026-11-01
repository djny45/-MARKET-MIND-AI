import unittest

from app.main import worker_runtime


class WorkerRuntimeApiTests(unittest.TestCase):
    def test_runtime_endpoint_reports_real_capability_boundary(self):
        result = worker_runtime()
        self.assertEqual(result["intelligence_core"], "shared_central_intelligence")
        self.assertEqual(result["worker_profile_count"], 550)
        self.assertIn("sma", result["routable_node_types"])
        self.assertFalse(result["llm_inference_enabled"])
        self.assertFalse(result["broker_execution"])


if __name__ == "__main__":
    unittest.main()
