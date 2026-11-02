import os
import unittest
from unittest.mock import patch

from app.intelligence_core import (
    IntelligenceCoreError,
    intelligence_core_status,
    synthesize_research,
)


class SharedIntelligenceCoreTests(unittest.TestCase):
    def test_default_mode_is_disabled_and_single_core(self):
        with patch.dict(os.environ, {}, clear=True):
            status = intelligence_core_status()
        self.assertEqual(status["core_id"], "shared_central_intelligence")
        self.assertFalse(status["enabled"])
        self.assertFalse(status["capabilities"]["worker_specific_models"])
        result = synthesize_research({"findings": ["fixture"]})
        self.assertEqual(result["status"], "not_configured")
        self.assertIsNone(result["summary"])

    def test_rejects_non_loopback_ollama_host(self):
        env = {"OLLAMA_BASE_URL": "http://example.com:11434",
               "INTELLIGENCE_CORE_ENABLED": "true"}
        with patch.dict(os.environ, env, clear=True), patch(
            "app.intelligence_core.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("203.0.113.4", 11434))],
        ):
            with self.assertRaises(IntelligenceCoreError):
                intelligence_core_status()

    def test_research_payload_is_bounded(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(IntelligenceCoreError):
                synthesize_research({"large": "x" * 25000})


if __name__ == "__main__":
    unittest.main()
