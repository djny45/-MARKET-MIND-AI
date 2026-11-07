import hashlib
import unittest

from app.open_source_intake import build_source_candidate


SHA = "a" * 40


class OpenSourceIntakeTests(unittest.TestCase):
    def candidate(self, **overrides):
        values = {
            "repository_url": "https://github.com/example/project",
            "commit_sha": SHA,
            "file_path": "docs/research.md",
            "license_spdx": "MIT",
            "content": "A source-linked research note.",
        }
        values.update(overrides)
        return build_source_candidate(**values)

    def test_candidate_is_pinned_and_review_only(self):
        item = self.candidate()
        self.assertEqual(item["repository_url"], "https://github.com/example/project")
        self.assertEqual(item["commit_sha"], SHA)
        self.assertEqual(item["review_status"], "pending")
        self.assertTrue(item["review_required"])
        self.assertFalse(item["execution_allowed"])
        self.assertFalse(item["automatic_copy_allowed"])
        self.assertFalse(item["automatic_promotion_allowed"])

    def test_digest_and_candidate_id_are_deterministic(self):
        first = self.candidate()
        second = self.candidate(repository_url="https://github.com/example/project/")
        self.assertEqual(first["content_sha256"], hashlib.sha256(
            first["content"].encode("utf-8")).hexdigest())
        self.assertEqual(first["candidate_id"], second["candidate_id"])

    def test_rejects_non_github_or_noncanonical_urls(self):
        for url in (
            "http://github.com/example/project",
            "https://github.com.evil.example/example/project",
            "https://user@github.com/example/project",
            "https://github.com/example/project/tree/main",
            "https://gitlab.com/example/project",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.candidate(repository_url=url)

    def test_rejects_invalid_commit_sha(self):
        for sha in ("main", "a" * 39, "g" * 40, "a" * 41):
            with self.subTest(sha=sha), self.assertRaises(ValueError):
                self.candidate(commit_sha=sha)

    def test_rejects_path_traversal_and_binary_files(self):
        for path in ("../secret.py", "docs/../secret.py", "/absolute/file.md",
                     "docs\\\\secret.md", "release.exe", "module.pyc"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.candidate(file_path=path)

    def test_rejects_unapproved_license(self):
        for license_id in ("Unknown", "GPL-3.0-only", "LicenseRef-custom"):
            with self.subTest(license_id=license_id), self.assertRaises(ValueError):
                self.candidate(license_spdx=license_id)

    def test_rejects_empty_binary_and_oversized_content(self):
        for content in ("", "   ", "a" * 50_001, "binary\\x00payload"):
            with self.subTest(content_length=len(content)), self.assertRaises(ValueError):
                self.candidate(content=content)

    def test_rejects_unsupported_source_kind(self):
        with self.assertRaises(ValueError):
            self.candidate(source_kind="executable")


if __name__ == "__main__":
    unittest.main()
