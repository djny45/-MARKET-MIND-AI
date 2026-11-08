import unittest
from unittest.mock import patch
import httpx

from app.github_research_discovery import discover_github_repositories


class GitHubResearchDiscoveryTests(unittest.TestCase):
    def payload(self, items):
        return {"total_count": len(items), "items": items}

    def repo(self, name="org/project"):
        return {
            "full_name": name, "html_url": "https://github.com/" + name,
            "description": "Research library", "stargazers_count": 123,
            "default_branch": "main", "license": {"spdx_id": "MIT"},
            "updated_at": "2026-01-01T00:00:00Z",
        }

    @patch("app.github_research_discovery.httpx.get")
    def test_returns_metadata_only_and_caps_items(self, get):
        get.return_value.json.return_value = self.payload([self.repo(), self.repo("org/other")])
        get.return_value.raise_for_status.return_value = None
        result = discover_github_repositories("quant research", 1)
        self.assertEqual(result["count"], 1)
        item = result["repositories"][0]
        self.assertEqual(item["license_spdx"], "MIT")
        self.assertFalse(item["source_content_fetched"])
        self.assertFalse(item["execution_allowed"])
        self.assertEqual(get.call_args.kwargs["params"]["per_page"], 1)
        self.assertFalse(get.call_args.kwargs["follow_redirects"])

    def test_rejects_invalid_query_and_limit(self):
        for query, limit in [("", 2), ("x" * 181, 2), ("hello", 0), ("hello", 11), ("hello", True)]:
            with self.assertRaises(ValueError):
                discover_github_repositories(query, limit)

    @patch("app.github_research_discovery.httpx.get")
    def test_rate_limit_is_reported_without_sensitive_response_body(self, get):
        response = httpx.Response(403, request=httpx.Request("GET", "https://api.github.com"))
        get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "forbidden", request=response.request, response=response
        )
        with self.assertRaisesRegex(RuntimeError, "rate limit"):
            discover_github_repositories("alpha")

    @patch("app.github_research_discovery.httpx.get")
    def test_timeout_is_handled(self, get):
        get.side_effect = httpx.TimeoutException("timeout")
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            discover_github_repositories("alpha")

    @patch("app.github_research_discovery.httpx.get")
    def test_unexpected_payload_rejected(self, get):
        get.return_value.raise_for_status.return_value = None
        get.return_value.json.return_value = {"items": "not-a-list"}
        with self.assertRaisesRegex(RuntimeError, "unexpected response"):
            discover_github_repositories("alpha")

    @patch("app.github_research_discovery.httpx.get")
    def test_malformed_items_are_skipped(self, get):
        get.return_value.raise_for_status.return_value = None
        get.return_value.json.return_value = self.payload([{}, self.repo()])
        result = discover_github_repositories("alpha")
        self.assertEqual(result["count"], 1)


if __name__ == "__main__":
    unittest.main()
