import os
import tempfile
import unittest
from unittest.mock import patch

from app.agent_council_api import (
    AgentCouncilRequest,
    AgentCouncilReviewRequest,
    run_council,
    review_council,
)


class AgentCouncilApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {
            "MARKET_MIND_DB": os.path.join(self.temp.name, "api-council.sqlite"),
            "INTELLIGENCE_CORE_ENABLED": "false",
        })
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_run_route_returns_bounded_council_report(self):
        result = run_council(AgentCouncilRequest(
            agent_ids=["worker_001", "worker_021"],
            brief="Review supplied figures",
            data={"source": "user_supplied"},
        ))
        self.assertEqual(result["agent_count_requested"], 2)
        self.assertFalse(result["paper_trading"])
        self.assertFalse(result["broker_execution"])

    def test_review_route_returns_output_fingerprints(self):
        result = review_council(AgentCouncilReviewRequest(council_result={
            "members": [
                {"agent_id": "a", "analysis": "Same result"},
                {"agent_id": "b", "analysis": "same   result"},
            ]
        }))
        self.assertEqual(result["unique_analysis_fingerprints"], 1)
        self.assertIsNone(result["consensus"])

    def test_invalid_agent_id_is_rejected_by_route(self):
        from fastapi import HTTPException
        with self.assertRaises(HTTPException) as caught:
            run_council(AgentCouncilRequest(
                agent_ids=["worker_9999"], brief="brief"
            ))
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
