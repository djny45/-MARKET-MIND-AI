import os
import unittest
from unittest.mock import patch

from app.freellmapi_adapter import (
    FreeLLMAPIConfigurationError,
    configured_freellmapi,
    build_chat_completion_request,
    extract_chat_completion_text,
)


class FreeLLMAPIAdapterTests(unittest.TestCase):
    def test_disabled_or_other_provider_does_not_activate(self):
        with patch.dict(os.environ, {"INTELLIGENCE_CORE_PROVIDER": "ollama",
                                    "INTELLIGENCE_CORE_ENABLED": "true"}, clear=True):
            self.assertIsNone(configured_freellmapi())

    def test_incomplete_config_returns_none(self):
        env = {"INTELLIGENCE_CORE_PROVIDER": "freellmapi",
               "INTELLIGENCE_CORE_ENABLED": "true",
               "FREELLMAPI_BASE_URL": "http://127.0.0.1:3001",
               "FREELLMAPI_MODEL": "model-id"}
        with patch.dict(os.environ, env, clear=True):
            self.assertIsNone(configured_freellmapi())

    def test_non_loopback_is_rejected(self):
        env = {"INTELLIGENCE_CORE_PROVIDER": "freellmapi",
               "INTELLIGENCE_CORE_ENABLED": "true",
               "FREELLMAPI_BASE_URL": "http://example.com:3001",
               "FREELLMAPI_API_KEY": "dummy-test-key",
               "FREELLMAPI_MODEL": "model-id"}
        with patch.dict(os.environ, env, clear=True), patch(
            "app.freellmapi_adapter.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("203.0.113.4", 3001))],
        ):
            with self.assertRaises(FreeLLMAPIConfigurationError):
                configured_freellmapi()

    def test_request_uses_openai_compatible_endpoint_and_bearer(self):
        url, body, headers = build_chat_completion_request(
            "http://127.0.0.1:3001", "test-key", "model-x", "hello"
        )
        self.assertEqual(url, "http://127.0.0.1:3001/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer test-key")
        self.assertIn(b'"stream": false', body)

    def test_extracts_chat_completion_content(self):
        self.assertEqual(
            extract_chat_completion_text({"choices": [{"message": {"content": " hi "}}]}),
            " hi ",
        )
        self.assertIsNone(extract_chat_completion_text({"choices": []}))


if __name__ == "__main__":
    unittest.main()
