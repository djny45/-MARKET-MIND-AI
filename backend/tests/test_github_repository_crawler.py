import json
import unittest

import httpx

from app.github_repository_crawler import (
    GitHubCrawlerError,
    fetch_repository_metadata,
)


def _response(payload, status=200, headers=None):
    return httpx.Response(
        status,
        headers=headers or {"content-type": "application/json"},
        content=json.dumps(payload).encode(),
    )


class GitHubRepositoryCrawlerTests(unittest.TestCase):
    def test_fetches_metadata_and_pins_default_branch_commit(self):
        calls = []

        def handler(request):
            calls.append(str(request.url))
            if request.url.path == "/repos/example/project":
                return _response({
                    "full_name": "example/project",
                    "description": "Demo repository",
                    "default_branch": "main",
                    "visibility": "public",
                    "archived": False,
                    "license": {"spdx_id": "MIT"},
                })
            if request.url.path == "/repos/example/project/commits/main":
                return _response({
                    "sha": "a" * 40,
                    "html_url": "https://github.com/example/project/commit/" + "a" * 40,
                    "commit": {"committer": {"date": "2026-01-01T00:00:00Z"}},
                })
            return _response({"message": "not found"}, status=404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        result = fetch_repository_metadata("https://github.com/example/project", client=client)

        self.assertEqual(result["pinned_commit"]["sha"], "a" * 40)
        self.assertEqual(result["repository"]["license_spdx_id"], "MIT")
        self.assertTrue(result["crawler_policy"]["metadata_only"])
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(url.startswith("https://api.github.com/") for url in calls))

    def test_rejects_redirect_responses(self):
        def handler(request):
            return httpx.Response(302, headers={"location": "https://attacker.invalid/"})

        client = httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=False)
        with self.assertRaises(GitHubCrawlerError):
            fetch_repository_metadata("https://github.com/example/project", client=client)

    def test_rejects_oversized_response(self):
        body = json.dumps({"description": "x" * 2000}).encode()

        def handler(request):
            return httpx.Response(200, headers={"content-length": str(len(body))}, content=body)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(GitHubCrawlerError):
            fetch_repository_metadata("https://github.com/example/project", client=client)

    def test_rejects_invalid_commit_sha(self):
        def handler(request):
            if request.url.path.endswith("/commits/main"):
                return _response({"sha": "not-a-sha"})
            return _response({"default_branch": "main", "full_name": "example/project"})

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(GitHubCrawlerError):
            fetch_repository_metadata("https://github.com/example/project", client=client)

    def test_rejects_untrusted_repository_url_before_request(self):
        def handler(request):
            raise AssertionError("no request should be made")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        with self.assertRaises(ValueError):
            fetch_repository_metadata("https://github.com.evil.invalid/example/project", client=client)


if __name__ == "__main__":
    unittest.main()
