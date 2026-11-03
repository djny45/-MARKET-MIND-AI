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


    def test_task_quality_endpoint_returns_not_evaluated_for_valid_task(self):
        import os
        import tempfile
        from unittest.mock import patch
        from app.analytical_agent_tasks import enqueue_research_task
        from app.main import analytical_agent_task_quality_evaluation
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(temp, "quality.sqlite")}):
                queued = enqueue_research_task("worker_018", "No quality eval")
                result = analytical_agent_task_quality_evaluation(queued["task_id"])
                self.assertEqual(result["status"], "not_evaluated")
                self.assertEqual(result["task_id"], queued["task_id"])

    def test_task_quality_endpoint_returns_404_for_unknown_task(self):
        from fastapi import HTTPException
        from app.main import analytical_agent_task_quality_evaluation
        with self.assertRaises(HTTPException) as raised:
            analytical_agent_task_quality_evaluation("missing-task")
        self.assertEqual(raised.exception.status_code, 404)

if __name__ == "__main__":
    unittest.main()
