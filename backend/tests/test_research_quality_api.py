import unittest

from app.main import ResearchQualityEvaluationRequest, evaluate_research_quality


class ResearchQualityApiTests(unittest.TestCase):
    def test_endpoint_returns_traceability_metrics(self):
        request = ResearchQualityEvaluationRequest(
            draft="Some claim; limitation: source meaning is not verified.",
            claims=[{"text": "Example claim", "source_refs": ["ref-a"]}],
            source_registry=[{"source_id": "ref-a"}],
        )
        result = evaluate_research_quality(request)
        self.assertEqual(result["evaluation_type"], "deterministic_research_traceability_check")
        self.assertEqual(result["metrics"]["known_source_reference_coverage"], 1.0)

    def test_endpoint_translates_invalid_evaluation_to_http_400(self):
        request = ResearchQualityEvaluationRequest(
            draft="   ",
            claims=[],
            source_registry=[],
        )
        with self.assertRaises(Exception) as raised:
            evaluate_research_quality(request)
        self.assertEqual(getattr(raised.exception, "status_code", None), 400)


if __name__ == "__main__":
    unittest.main()
