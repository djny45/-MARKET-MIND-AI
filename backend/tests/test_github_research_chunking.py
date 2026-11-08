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

    def test_manifest_hashes_offsets_and_overlap_are_consistent(self):
        import hashlib

        text = ("alpha beta gamma delta\n" * 50)
        manifest = chunk_research_text(text, max_chars=300, overlap_chars=40)
        source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        self.assertEqual(manifest["source_sha256"], source_hash)
        self.assertEqual(manifest["source_chars"], len(text))
        self.assertEqual(manifest["chunk_count"], len(manifest["chunks"]))
        self.assertFalse(manifest["semantic_extraction"])
        self.assertFalse(manifest["instruction_injection"])
        self.assertFalse(manifest["auto_promotion"])

        for index, chunk in enumerate(manifest["chunks"]):
            self.assertEqual(chunk["index"], index)
            self.assertEqual(chunk["source_sha256"], source_hash)
            self.assertEqual(chunk["text"], text[chunk["start_char"]:chunk["end_char"]])
            self.assertEqual(
                chunk["sha256"],
                hashlib.sha256(chunk["text"].encode("utf-8")).hexdigest(),
            )
            self.assertLessEqual(len(chunk["text"]), manifest["max_chars"])
            if index:
                previous = manifest["chunks"][index - 1]
                self.assertEqual(
                    chunk["start_char"],
                    previous["end_char"] - manifest["overlap_chars"],
                )

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
