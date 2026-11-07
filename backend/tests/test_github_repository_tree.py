"""Regression tests for pinned metadata-only GitHub tree scanning."""
import unittest

import httpx

from app.github_repository_tree import scan_repository_tree
from app.github_repository_crawler import GitHubCrawlerError


def _client(tree_payload):
    sha = "a" * 40

    def handler(request):
        path = request.url.path
        if path == "/repos/acme/demo":
            payload = {"full_name": "acme/demo", "default_branch": "main", "license": None}
        elif path == "/repos/acme/demo/commits/main":
            payload = {
                "sha": sha,
                "html_url": "https://github.com/acme/demo/commit/" + sha,
                "commit": {"committer": {"date": "2026-11-08T00:00:00Z"}},
            }
        elif path == f"/repos/acme/demo/git/trees/{sha}":
            payload = tree_payload
        else:
            return httpx.Response(404, json={"message": "unexpected endpoint"})
        return httpx.Response(200, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


class RepositoryTreeScannerTests(unittest.TestCase):
    def test_scan_tree_pins_commit_and_classifies_manifest_paths(self):
        client = _client({
            "sha": "tree-sha",
            "truncated": False,
            "tree": [
                {"path": "README.md", "type": "blob", "sha": "b" * 40, "size": 100},
                {"path": "backend/app/main.py", "type": "blob", "sha": "c" * 40, "size": 200},
                {"path": "requirements.txt", "type": "blob", "sha": "d" * 40, "size": 30},
                {"path": "docs", "type": "tree", "sha": "e" * 40},
                {"path": "vendor/submodule", "type": "commit", "sha": "f" * 40},
            ],
        })
        try:
            result = scan_repository_tree("https://github.com/acme/demo", client=client)
        finally:
            client.close()

        assert result["pinned_commit_sha"] == "a" * 40
        assert result["entry_count"] == 5
        assert result["dependency_manifests"] == ["requirements.txt"]
        assert "README.md" in result["documentation_paths"]
        assert result["scanner_policy"]["repository_code_executed"] is False
        source = next(item for item in result["entries"] if item["path"].endswith("main.py"))
        assert source["language"] == "Python"
        assert source["category"] == "source"


    def test_scan_tree_rejects_truncated_manifest(self):
        client = _client({"sha": "tree-sha", "truncated": True, "tree": []})
        try:
            with self.assertRaisesRegex(GitHubCrawlerError, "truncated"):
                scan_repository_tree("https://github.com/acme/demo", client=client)
        finally:
            client.close()


    def test_scan_tree_rejects_non_github_repository_url(self):
        with self.assertRaises(ValueError):
            scan_repository_tree("https://github.com.evil.example/acme/demo")


    def test_scan_tree_rejects_entry_over_limit(self):
        from app.github_repository_tree import MAX_TREE_ENTRIES

        client = _client({
            "sha": "tree-sha",
            "truncated": False,
            "tree": [{"path": f"file-{i}.txt", "type": "blob", "sha": "b" * 40, "size": 1}
                     for i in range(MAX_TREE_ENTRIES + 1)],
        })
        try:
            with unittest.TestCase().assertRaisesRegex(GitHubCrawlerError, "entry limit"):
                scan_repository_tree("https://github.com/acme/demo", client=client)
        finally:
            client.close()
