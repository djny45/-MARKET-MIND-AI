import unittest

from app.main import ResearchOrchestrationRequest, orchestrate_research_request


class ResearchOrchestratorApiTests(unittest.TestCase):
    def test_endpoint_accepts_citation_claims_and_returns_audit(self):
        request = ResearchOrchestrationRequest(
            nodes=[{
                "id": "feed",
                "type": "market_input",
                "data": {"values": [2, 3, 4]},
            }],
            citation_claims=[{
                "text": "The source contains the supplied excerpt.",
                "citations": [{
                    "source_id": "s1",
                    "excerpt": "supplied excerpt",
                }],
            }],
            source_registry=[{
                "source_id": "s1",
                "text": "The source contains the supplied excerpt.",
            }],
        )
        result = orchestrate_research_request(request)
        audit = result["report"]["citation_audit"]
        self.assertEqual(audit["status"], "passed")
        self.assertEqual(audit["metrics"]["claim_citation_coverage"], 1.0)

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
