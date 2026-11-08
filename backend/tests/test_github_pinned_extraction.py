import base64
import unittest
from unittest.mock import patch

import httpx
from app.github_pinned_extraction import fetch_pinned_text_candidate


SHA = "c" * 40


class GitHubPinnedExtractionTests(unittest.TestCase):
    def commit(self):
        return {"sha": SHA}

    def file(self, text="documentation excerpt"):
        raw = text.encode("utf-8")
        return {"type": "file", "size": len(raw), "encoding": "base64",
                "content": base64.b64encode(raw).decode("ascii")}

    @patch("app.github_pinned_extraction._get_json")
    def test_fetches_commit_pinned_text_and_hashes_it(self, get):
        get.side_effect = [self.commit(), self.file()]
        result = fetch_pinned_text_candidate(
            repository_url="https://github.com/org/repo", commit_sha=SHA,
            file_path="docs/guide.md", license_spdx="MIT",
        )
        self.assertEqual(result["commit_sha"], SHA)
        self.assertEqual(result["content"], "documentation excerpt")
        self.assertEqual(len(result["content_sha256"]), 64)
        self.assertTrue(result["review_required"])
        self.assertFalse(result["execution_allowed"])
        self.assertEqual(get.call_count, 2)

    @patch("app.github_pinned_extraction._get_json")
    def test_rejects_commit_sha_mismatch(self, get):
        get.return_value = {"sha": "d" * 40}
        with self.assertRaisesRegex(ValueError, "did not match"):
            fetch_pinned_text_candidate(
                repository_url="https://github.com/org/repo", commit_sha=SHA,
                file_path="README.md", license_spdx="MIT",
            )

    @patch("app.github_pinned_extraction._get_json")
    def test_rejects_oversized_file_before_decode(self, get):
        get.side_effect = [self.commit(), {"type": "file", "size": 50001,
                                           "encoding": "base64", "content": ""}]
        with self.assertRaisesRegex(ValueError, "exceeds"):
            fetch_pinned_text_candidate(
                repository_url="https://github.com/org/repo", commit_sha=SHA,
                file_path="README.md", license_spdx="MIT",
            )

    @patch("app.github_pinned_extraction._get_json")
    def test_rejects_binary_or_non_utf8(self, get):
        get.side_effect = [self.commit(), {"type": "file", "size": 2,
            "encoding": "base64", "content": base64.b64encode(b"\x00x").decode()}]
        with self.assertRaisesRegex(ValueError, "binary"):
            fetch_pinned_text_candidate(
                repository_url="https://github.com/org/repo", commit_sha=SHA,
                file_path="README.md", license_spdx="MIT",
            )

    def test_rejects_path_traversal_and_non_github_url(self):
        for url, path in [("https://evil.example/org/repo", "README.md"),
                          ("https://github.com/org/repo", "../secret")]:
            with self.assertRaises(ValueError):
                fetch_pinned_text_candidate(
                    repository_url=url, commit_sha=SHA, file_path=path,
                    license_spdx="MIT",
                )


if __name__ == "__main__":
    unittest.main()
