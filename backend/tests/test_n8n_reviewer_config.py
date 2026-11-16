import os
import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.n8n_reviewer_security import _n8n_config


class N8NConfigurationBoundaryTests(unittest.TestCase):
    def _config(self, **overrides):
        values = {
            "N8N_BASE_URL": "https://n8n.example.test",
            "N8N_API_KEY": "test-api-key",
        }
        values.update(overrides)
        with patch.dict(os.environ, values, clear=True):
            return _n8n_config()

    def test_https_instance_root_is_normalized(self):
        base, key = self._config()
        self.assertEqual(base, "https://n8n.example.test/api/v1")
        self.assertEqual(key, "test-api-key")

    def test_existing_api_v1_suffix_is_not_duplicated(self):
        base, _ = self._config(N8N_BASE_URL="https://n8n.example.test/api/v1/")
        self.assertEqual(base, "https://n8n.example.test/api/v1")

    def test_local_http_is_allowed_for_self_hosted_development(self):
        base, _ = self._config(N8N_BASE_URL="http://n8n:5678")
        self.assertEqual(base, "http://n8n:5678/api/v1")

    def test_untrusted_plain_http_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            self._config(N8N_BASE_URL="http://public.example.test")
        self.assertEqual(error.exception.status_code, 503)

    def test_url_credentials_are_rejected(self):
        with self.assertRaises(HTTPException):
            self._config(N8N_BASE_URL="https://user:password@n8n.example.test")

    def test_query_and_fragment_are_rejected(self):
        for url in (
            "https://n8n.example.test?target=internal",
            "https://n8n.example.test/#fragment",
        ):
            with self.subTest(url=url), self.assertRaises(HTTPException):
                self._config(N8N_BASE_URL=url)

    def test_arbitrary_api_paths_are_rejected(self):
        with self.assertRaises(HTTPException):
            self._config(N8N_BASE_URL="https://n8n.example.test/custom/path")

    def test_missing_api_key_fails_closed(self):
        with self.assertRaises(HTTPException) as error:
            self._config(N8N_API_KEY="")
        self.assertEqual(error.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
