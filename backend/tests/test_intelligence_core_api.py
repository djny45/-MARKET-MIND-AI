import os
import unittest
from unittest.mock import patch

from app.main import intelligence_core, intelligence_core_synthesis, ResearchSynthesisRequest


class IntelligenceCoreApiTests(unittest.TestCase):
    def test_status_endpoint_reports_disabled_shared_core_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            result = intelligence_core()
        self.assertEqual(result["core_id"], "shared_central_intelligence")
        self.assertFalse(result["enabled"])
        self.assertEqual(result["provider"], "none")

    def test_synthesis_endpoint_passes_only_supplied_research(self):
        research = {"symbol": "DEMO", "observations": [{"close": 123.4}]}
        expected = {"status": "completed", "summary": "fixture summary"}
        with patch("app.main.synthesize_research", return_value=expected) as synthesize:
            result = intelligence_core_synthesis(ResearchSynthesisRequest(research=research))
        synthesize.assert_called_once_with(research)
        self.assertEqual(result, expected)

    def test_synthesis_endpoint_translates_core_configuration_errors(self):
        from fastapi import HTTPException
        from app.intelligence_core import IntelligenceCoreError

        with patch("app.main.synthesize_research", side_effect=IntelligenceCoreError("provider config invalid")):
            with self.assertRaises(HTTPException) as caught:
                intelligence_core_synthesis(ResearchSynthesisRequest(research={"fixture": True}))
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
