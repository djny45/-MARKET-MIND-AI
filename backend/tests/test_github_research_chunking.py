import unittest

from app.github_research_chunking import chunk_research_text


class GitHubResearchChunkingTests(unittest.TestCase):
    def test_chunks_are_deterministic_and_have_source_offsets(self):
        text = ("A line of documentation.\n" * 40)
        first = chunk_research_text(text, max_chars=300, overlap_chars=30)
        second = chunk_research_text(text, max_chars=300, overlap_chars=30)
        self.assertEqual(first, second)
        self.assertGreater(first["chunk_count"], 1)
        self.assertTrue(all(len(item["sha256"]) == 64 for item in first["chunks"]))
        self.assertEqual(first["chunks"][0]["start_char"], 0)
        self.assertEqual(first["chunks"][-1]["end_char"], len(text))

    def test_rejects_bad_limits_and_large_input(self):
        for kwargs in [{"max_chars": 100}, {"max_chars": 300, "overlap_chars": 200}]:
            with self.assertRaises(ValueError):
                chunk_research_text("some content", **kwargs)
        with self.assertRaisesRegex(ValueError, "50000-byte"):
            chunk_research_text("x" * 50001)

    def test_rejects_chunk_count_that_would_overflow_manifest(self):
        with self.assertRaisesRegex(ValueError, "100-chunk"):
            chunk_research_text("x" * 50000, max_chars=200, overlap_chars=0)

    def test_rejects_empty_text(self):
        with self.assertRaises(ValueError):
            chunk_research_text("  ")


if __name__ == "__main__":
    unittest.main()
