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

    def test_ollama_url_rejects_credentials_query_fragment_and_path(self):
        base_env = {"INTELLIGENCE_CORE_ENABLED": "true"}
        for url in (
            "http://user:pass@127.0.0.1:11434",
            "http://127.0.0.1:11434?token=oops",
            "http://127.0.0.1:11434#fragment",
            "http://127.0.0.1:11434/custom",
        ):
            with self.subTest(url=url), patch.dict(
                os.environ, {**base_env, "OLLAMA_BASE_URL": url}, clear=True
            ):
                with self.assertRaises(IntelligenceCoreError):
                    intelligence_core_status()

    def test_ollama_url_rejects_invalid_port(self):
        env = {"INTELLIGENCE_CORE_ENABLED": "true",
               "OLLAMA_BASE_URL": "http://127.0.0.1:99999"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaisesRegex(IntelligenceCoreError, "invalid port"):
                intelligence_core_status()

    def test_ollama_rejects_arbitrary_hostname_even_if_loopback_resolves(self):
        env = {"INTELLIGENCE_CORE_ENABLED": "true",
               "OLLAMA_BASE_URL": "http://rebind.example:11434"}
        with patch.dict(os.environ, env, clear=True), patch(
            "socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 11434))],
        ):
            with self.assertRaises(IntelligenceCoreError):
                intelligence_core_status()

    def test_research_input_must_be_json_object(self):
        with patch("app.intelligence_core.intelligence_core_status") as status:
            for invalid in ([], "research", 123, None):
                with self.subTest(invalid=invalid):
                    with self.assertRaisesRegex(
                        IntelligenceCoreError, "JSON object"
                    ):
                        synthesize_research(invalid)
            status.assert_not_called()

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

    def test_research_payload_rejects_non_json_numeric_values(self):
        enabled_status = {"enabled": True, "model": "phi3"}
        with patch("app.intelligence_core.intelligence_core_status", return_value=enabled_status):
            with self.assertRaisesRegex(IntelligenceCoreError, "JSON-safe"):
                synthesize_research({"invalid_number": float("nan")})

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
        response.headers = {"X-Routed-Via": "groq%2Fllama-test", "X-Fallback-Attempts": "2"}
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
        prompt_text = json.dumps(sent)
        self.assertIn("metadata completeness separately from source credibility", prompt_text)
        self.assertIn("manual review leads only", prompt_text)
        self.assertIn("Do not infer contradiction, consensus, or truth", prompt_text)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["provider"], "freellmapi_local")
        self.assertEqual(result["summary"], "Concise summary")
        self.assertEqual(result["routed_via"], "groq/llama-test")
        self.assertEqual(result["fallback_attempts"], "2")

    def test_provider_telemetry_is_bounded_and_validated(self):
        import json
        from unittest.mock import Mock

        env = {"INTELLIGENCE_CORE_ENABLED": "true",
               "INTELLIGENCE_CORE_PROVIDER": "freellmapi"}
        response = Mock()
        response.read.return_value = json.dumps({
            "choices": [{"message": {"content": "ok"}}]
        }).encode("utf-8")
        response.headers = {
            "X-Routed-Via": "x" * 500,
            "X-Fallback-Attempts": "9" * 500,
        }
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, env, clear=True), patch(
            "app.intelligence_core.intelligence_core_status",
            return_value={"enabled": True, "model": "test-model"},
        ), patch(
            "app.intelligence_core.configured_freellmapi",
            return_value=("http://127.0.0.1:3001", "test-key", "test-model"),
        ):
            result = synthesize_research(
                {"facts": []}, opener=Mock(return_value=response)
            )

        self.assertEqual(len(result["routed_via"]), 120)
        self.assertIsNone(result["fallback_attempts"])

    def test_ollama_rejects_non_object_json_response(self):
        import json
        from unittest.mock import Mock

        env = {
            "INTELLIGENCE_CORE_ENABLED": "true",
            "INTELLIGENCE_CORE_PROVIDER": "ollama",
        }
        response = Mock()
        response.read.return_value = json.dumps([]).encode("utf-8")
        response.headers = {}
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, env, clear=True), patch(
            "app.intelligence_core.intelligence_core_status",
            return_value={"enabled": True, "model": "phi3"},
        ), patch(
            "app.intelligence_core._ollama_url",
            return_value="http://127.0.0.1:11434",
        ):
            result = synthesize_research(
                {"facts": []}, opener=Mock(return_value=response)
            )

        self.assertEqual(result["status"], "invalid_provider_response")
        self.assertIsNone(result["summary"])
        self.assertIn("unexpected JSON structure", result["reason"])

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
