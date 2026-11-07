import unittest

from app.open_source_intake import (
    build_open_source_intake,
    normalize_github_repository_url,
)


class OpenSourceIntakeTests(unittest.TestCase):
    def test_normalizes_git_suffix_and_trailing_slash(self):
        self.assertEqual(
            normalize_github_repository_url("https://github.com/org/project.git/"),
            "https://github.com/org/project",
        )

    def test_rejects_non_github_and_non_https_urls(self):
        for url in (
            "http://github.com/org/project",
            "https://github.com.evil.test/org/project",
            "https://gitlab.com/org/project",
            "https://user:pass@github.com/org/project",
            "https://github.com:8443/org/project",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_github_repository_url(url)

    def test_rejects_subpaths_query_and_fragment(self):
        for url in (
            "https://github.com/org/project/tree/main",
            "https://github.com/org/project?tab=readme",
            "https://github.com/org/project#readme",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_github_repository_url(url)

    def test_rejects_empty_and_oversized_inputs(self):
        for url in ("", "  ", "https://github.com/" + "x" * 2100):
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_github_repository_url(url)

    def test_unknown_license_blocks_reuse_and_execution(self):
        plan = build_open_source_intake("https://github.com/org/project")
        self.assertEqual(plan["license_status"], "unknown_block_reuse")
        self.assertFalse(plan["reuse_allowed"])
        self.assertFalse(plan["execution_allowed"])
        self.assertFalse(plan["auto_merge_allowed"])
        self.assertEqual(plan["intake_status"], "pending_review")

    def test_license_identifier_is_not_treated_as_approval(self):
        plan = build_open_source_intake(
            "https://github.com/org/project", license_id="MIT"
        )
        self.assertEqual(plan["license_id"], "MIT")
        self.assertEqual(plan["license_status"], "identified_needs_text_review")
        self.assertFalse(plan["reuse_allowed"])
        self.assertIn("pinned_commit_sha", plan["required_evidence"])


if __name__ == "__main__":
    unittest.main()
