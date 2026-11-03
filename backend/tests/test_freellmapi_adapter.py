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

    def test_base_url_rejects_query_fragment_and_unexpected_path(self):
        base_env = {"INTELLIGENCE_CORE_PROVIDER": "freellmapi",
                    "INTELLIGENCE_CORE_ENABLED": "true",
                    "FREELLMAPI_API_KEY": "dummy-test-key",
                    "FREELLMAPI_MODEL": "model-id"}
        for base_url in ("http://127.0.0.1:3001/v1?token=oops",
                         "http://127.0.0.1:3001/v1#fragment",
                         "http://127.0.0.1:3001/custom"):
            with self.subTest(base_url=base_url), patch.dict(
                os.environ, {**base_env, "FREELLMAPI_BASE_URL": base_url}, clear=True
            ):
                with self.assertRaises(FreeLLMAPIConfigurationError):
                    configured_freellmapi()

    def test_invalid_port_returns_configuration_error(self):
        env = {"INTELLIGENCE_CORE_PROVIDER": "freellmapi",
               "INTELLIGENCE_CORE_ENABLED": "true",
               "FREELLMAPI_BASE_URL": "http://127.0.0.1:99999",
               "FREELLMAPI_API_KEY": "dummy-test-key",
               "FREELLMAPI_MODEL": "model-id"}
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(FreeLLMAPIConfigurationError):
                configured_freellmapi()

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

    def test_arbitrary_hostname_is_rejected_even_if_it_resolves_to_loopback(self):
        env = {"INTELLIGENCE_CORE_PROVIDER": "freellmapi",
               "INTELLIGENCE_CORE_ENABLED": "true",
               "FREELLMAPI_BASE_URL": "http://rebind.example:3001",
               "FREELLMAPI_API_KEY": "dummy-test-key",
               "FREELLMAPI_MODEL": "model-id"}
        with patch.dict(os.environ, env, clear=True), patch(
            "app.freellmapi_adapter.socket.getaddrinfo",
            return_value=[(2, 1, 6, "", ("127.0.0.1", 3001))],
        ):
            with self.assertRaises(FreeLLMAPIConfigurationError):
                configured_freellmapi()

    def test_base_url_with_v1_path_does_not_duplicate_api_prefix(self):
        url, _, _ = build_chat_completion_request(
            "http://127.0.0.1:3001/v1", "test-key", "model-x", "hello"
        )
        self.assertEqual(url, "http://127.0.0.1:3001/v1/chat/completions")

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
