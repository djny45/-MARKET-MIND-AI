"""Tests for bounded allowlisted README/license/dependency retrieval."""
import base64
import unittest
import hashlib

import httpx

from app.github_repository_files import fetch_review_files, MAX_FILE_BYTES
from app.github_repository_crawler import GitHubCrawlerError


SHA = "a" * 40


def _client():
    contents = {
        "README.md": b"# Sample project\nThis is documentation.\n",
        "requirements.txt": b"fastapi>=0.1\nhttpx>=0.2\n",
    }

    def handler(request):
        path = request.url.path
        if path == "/repos/acme/demo":
            return httpx.Response(200, json={
                "full_name": "acme/demo", "default_branch": "main", "license": None,
            })
        if path == "/repos/acme/demo/commits/main":
            return httpx.Response(200, json={
                "sha": SHA, "html_url": "https://github.com/acme/demo/commit/" + SHA,
                "commit": {"committer": {"date": "2026-11-08T00:00:00Z"}},
            })
        if path == f"/repos/acme/demo/git/trees/{SHA}":
            return httpx.Response(200, json={
                "sha": "tree-sha", "truncated": False,
                "tree": [
                    {"path": "README.md", "type": "blob", "sha": "b" * 40,
                     "size": len(contents["README.md"])},
                    {"path": "requirements.txt", "type": "blob", "sha": "c" * 40,
                     "size": len(contents["requirements.txt"])},
                    {"path": "backend/app.py", "type": "blob", "sha": "d" * 40, "size": 100},
                ],
            })
        if "/contents/" in path:
            file_path = path.split("/contents/", 1)[1]
            raw = contents[file_path]
            return httpx.Response(200, json={
                "path": file_path, "sha": "e" * 40, "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii"),
            })
        return httpx.Response(404, json={"message": "unexpected endpoint"})

    return httpx.Client(transport=httpx.MockTransport(handler))


class RepositoryReviewFilesTests(unittest.TestCase):
    def test_fetch_review_files_only_returns_allowlisted_text_and_hashes(self):
        client = _client()
        try:
            result = fetch_review_files("https://github.com/acme/demo", client=client)
        finally:
            client.close()

        assert result["pinned_commit_sha"] == SHA
        assert result["retrieved_file_count"] == 2
        readme = next(item for item in result["files"] if item["path"] == "README.md")
        assert readme["content"].startswith("# Sample project")
        assert readme["sha256"] == hashlib.sha256(readme["content"].encode()).hexdigest()
        assert all(item["path"] != "backend/app.py" for item in result["files"])
        assert result["retrieval_policy"]["repository_code_executed"] is False


    def test_review_file_allowlist_is_not_bypassed(self):
        from app.github_repository_files import _is_allowlisted

        assert _is_allowlisted("docs/README.md")
        assert _is_allowlisted("requirements.txt")
        assert not _is_allowlisted("backend/app.py")
        assert not _is_allowlisted(".env")


    def test_decode_rejects_oversized_contents(self):
        from app.github_repository_files import _decode_contents

        payload = {
            "path": "README.md", "encoding": "base64",
            "content": base64.b64encode(b"x" * (MAX_FILE_BYTES + 1)).decode("ascii"),
        }
        with self.assertRaisesRegex(GitHubCrawlerError, "per-file size"):
            _decode_contents(payload, expected_path="README.md")


    def test_decode_rejects_path_mismatch(self):
        from app.github_repository_files import _decode_contents

        with unittest.TestCase().assertRaisesRegex(GitHubCrawlerError, "mismatched path"):
            _decode_contents({"path": "wrong.md"}, expected_path="README.md")
