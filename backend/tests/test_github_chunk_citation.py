import unittest
from app.github_research_chunking import chunk_research_text
from app.github_chunk_citation import build_chunk_citation


class GitHubChunkCitationTests(unittest.TestCase):
    def setUp(self):
        self.source = "intro\n" + ("A traceable source phrase with context.\n" * 20)
        self.manifest = chunk_research_text(self.source, max_chars=300, overlap_chars=30)

    def test_builds_citation_with_chunk_and_source_hashes(self):
        chunk = self.manifest["chunks"][0]
        phrase = "A traceable source phrase"
        result = build_chunk_citation(source_id="doc-1", manifest=self.manifest,
                                     chunk_index=0, excerpt=phrase)
        self.assertEqual(result["source_id"], "doc-1")
        self.assertEqual(result["excerpt"], phrase)
        self.assertEqual(result["chunk_sha256"], chunk["sha256"])
        self.assertEqual(result["source_sha256"], self.manifest["source_sha256"])
        self.assertTrue(result["human_review_required"])
        self.assertFalse(result["semantic_support_verified"])

    def test_rejects_excerpt_not_in_selected_chunk(self):
        with self.assertRaisesRegex(ValueError, "exact substring"):
            build_chunk_citation(source_id="doc-1", manifest=self.manifest,
                                 chunk_index=0, excerpt="invented quote")

    def test_rejects_tampered_chunk_hash(self):
        manifest = dict(self.manifest)
        manifest["chunks"] = [dict(x) for x in self.manifest["chunks"]]
        manifest["chunks"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "hash"):
            build_chunk_citation(source_id="doc-1", manifest=manifest,
                                 chunk_index=0, excerpt="A traceable source phrase")

    def test_rejects_invalid_index_and_source_hash(self):
        with self.assertRaisesRegex(ValueError, "chunk_index"):
            build_chunk_citation(source_id="doc-1", manifest=self.manifest,
                                 chunk_index=True, excerpt="phrase")
        bad = dict(self.manifest)
        bad["source_sha256"] = "not-a-hash"
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            build_chunk_citation(source_id="doc-1", manifest=bad,
                                 chunk_index=0, excerpt="phrase")


if __name__ == "__main__":
    unittest.main()
