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
        # Patch the standard-library socket module directly. This is resilient
        # to the core changing how it imports/re-exports socket.
        with patch.dict(os.environ, env, clear=True), patch(
            "socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("203.0.113.4", 11434))],
        ):
            with self.assertRaises(IntelligenceCoreError):
                intelligence_core_status()

    def test_research_payload_is_bounded(self):
        enabled_status = {
            "enabled": True,
            "model": "phi3",
        }
        with patch("app.intelligence_core.intelligence_core_status", return_value=enabled_status), patch(
            "app.intelligence_core._configured_url", return_value="http://127.0.0.1:11434"
        ):
            with self.assertRaises(IntelligenceCoreError):
                synthesize_research({"large": "x" * 30000})

    def test_freellmapi_synthesis_sends_request_and_returns_summary(self):
        import json
        from unittest.mock import Mock

        env = {
            "INTELLIGENCE_CORE_ENABLED": "true",
            "INTELLIGENCE_CORE_PROVIDER": "freellmapi",
        }
        response = Mock()
        response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "Concise summary"}}]
        }).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        opener = Mock(return_value=response)

        with patch.dict(os.environ, env, clear=True), patch(
            "app.intelligence_core.intelligence_core_status",
            return_value={"enabled": True, "model": "test-model"},
        ), patch(
            "app.intelligence_core.configured_freellmapi",
            return_value=("http://127.0.0.1:3001", "test-key", "test-model"),
        ):
            result = synthesize_research({"facts": ["source-backed fact"]}, opener=opener)

        request = opener.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:3001/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")
        sent = json.loads(request.data.decode("utf-8"))
        self.assertEqual(sent["model"], "test-model")
        self.assertFalse(sent["stream"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["provider"], "freellmapi_local")
        self.assertEqual(result["summary"], "Concise summary")

    def test_freellmapi_unavailable_returns_safe_fallback(self):
        from urllib.error import URLError
        from unittest.mock import Mock

        env = {"INTELLIGENCE_CORE_ENABLED": "true",
               "INTELLIGENCE_CORE_PROVIDER": "freellmapi"}
        with patch.dict(os.environ, env, clear=True), patch(
            "app.intelligence_core.intelligence_core_status",
            return_value={"enabled": True, "model": "test-model"},
        ), patch(
            "app.intelligence_core.configured_freellmapi",
            return_value=("http://127.0.0.1:3001", "test-key", "test-model"),
        ):
            result = synthesize_research(
                {"facts": []}, opener=Mock(side_effect=URLError("offline"))
            )
        self.assertEqual(result["status"], "provider_unavailable")
        self.assertIsNone(result["summary"])
        self.assertTrue(result["reason"])


if __name__ == "__main__":
    unittest.main()
