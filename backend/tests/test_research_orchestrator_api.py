import unittest

from app.main import ResearchOrchestrationRequest, orchestrate_research_request


class ResearchOrchestratorApiTests(unittest.TestCase):
    def test_endpoint_function_returns_single_core_report(self):
        request = ResearchOrchestrationRequest(
            nodes=[
                {"id": "feed", "type": "market_input",
                 "data": {"values": [2, 3, 4, 5]}},
                {"id": "summary", "type": "research_summary", "data": {}},
            ],
            edges=[{"source": "feed", "target": "summary"}],
        )
        result = orchestrate_research_request(request)
        self.assertEqual(result["orchestration_status"], "completed")
        self.assertEqual(result["report"]["summary"]["tasks_completed"], 2)
        self.assertFalse(result["capabilities"]["broker_execution"])


if __name__ == "__main__":
    unittest.main()
