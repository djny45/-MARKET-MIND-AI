import unittest

from app.research_citation_audit import audit_claim_citations


class ResearchCitationAuditTests(unittest.TestCase):
    def test_exact_excerpt_matches_registry_source_text(self):
        result = audit_claim_citations(
            claims=[{
                "text": "A cited factual claim.",
                "citations": [{"source_id": "s1", "excerpt": "Exact source phrase."}],
            }],
            source_registry=[{
                "source_id": "s1", "title": "Fixture source",
                "url": "https://example.invalid/source",
                "text": "Context before. Exact source phrase. Context after.",
            }],
        )
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["metrics"]["claim_citation_coverage"], 1.0)
        self.assertEqual(result["claims"][0]["citations"][0]["status"], "exact_excerpt_match")

    def test_unknown_source_and_nonmatching_excerpt_need_review(self):
        result = audit_claim_citations(
            claims=[{
                "text": "Claim.",
                "citations": [
                    {"source_id": "missing", "excerpt": "some quote"},
                    {"source_id": "s1", "excerpt": "not in the source"},
                ],
            }],
            source_registry=[{"source_id": "s1", "text": "actual source text"}],
        )
        self.assertEqual(result["status"], "needs_review")
        statuses = [item["status"] for item in result["claims"][0]["citations"]]
        self.assertEqual(statuses, ["unknown_source_id", "excerpt_not_found"])

    def test_source_text_missing_is_not_assumed_to_match(self):
        result = audit_claim_citations(
            claims=[{"text": "Claim.", "citations": [{"source_id": "s1", "excerpt": "quote"}]}],
            source_registry=[{"source_id": "s1", "title": "Metadata only"}],
        )
        self.assertEqual(result["claims"][0]["citations"][0]["status"], "source_text_unavailable")
        self.assertEqual(result["status"], "needs_review")

    def test_empty_claims_and_duplicate_source_ids_are_handled(self):
        result = audit_claim_citations(claims=[], source_registry=[])
        self.assertEqual(result["status"], "needs_review")
        with self.assertRaisesRegex(ValueError, "unique"):
            audit_claim_citations(
                claims=[],
                source_registry=[{"source_id": "s1"}, {"source_id": "s1"}],
            )

    def test_rejects_invalid_claim_or_citation_bounds(self):
        with self.assertRaisesRegex(ValueError, "claim text"):
            audit_claim_citations(claims=[{"text": ""}], source_registry=[])
        with self.assertRaisesRegex(ValueError, "citations"):
            audit_claim_citations(
                claims=[{"text": "Claim", "citations": [{}] * 21}],
                source_registry=[],
            )


    def test_chunk_provenance_hash_and_offsets_are_verified(self):
        import hashlib
        source_text = "prefix exact quote suffix"
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        claim = {"text": "Claim.", "citations": [{
            "source_id": "src", "excerpt": "exact quote",
            "source_sha256": source_hash, "chunk_sha256": source_hash,
            "chunk_text": source_text, "chunk_index": 0, "source_start_char": 0,
            "source_end_char": len(source_text),
            "excerpt_start_char": 7, "excerpt_end_char": 18,
        }]}
        result = audit_claim_citations(
            claims=[claim], source_registry=[{"source_id": "src", "text": source_text}],
        )
        citation = result["claims"][0]["citations"][0]
        self.assertEqual(citation["status"], "exact_excerpt_match")
        self.assertTrue(citation["chunk_provenance_verified"])
        self.assertEqual(citation["chunk_provenance_status"],
                         "verified_source_hash_and_excerpt_offsets")

    def test_invalid_chunk_index_blocks_provenance_verification(self):
        import hashlib
        source_text = "prefix exact quote suffix"
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        for invalid_index in (-1, True, 1.5):
            with self.subTest(chunk_index=invalid_index):
                result = audit_claim_citations(
                    claims=[{"text": "Claim.", "citations": [{
                        "source_id": "src", "excerpt": "exact quote",
                        "source_sha256": source_hash,
                        "chunk_sha256": source_hash,
                        "chunk_text": source_text,
                        "chunk_index": invalid_index,
                        "source_start_char": 0,
                        "source_end_char": len(source_text),
                        "excerpt_start_char": 7,
                        "excerpt_end_char": 18,
                    }]}],
                    source_registry=[{"source_id": "src", "text": source_text}],
                )
                citation = result["claims"][0]["citations"][0]
                self.assertEqual(citation["status"], "provenance_mismatch")
                self.assertFalse(citation["chunk_provenance_verified"])
                self.assertEqual(result["status"], "needs_review")

    def test_chunk_provenance_mismatch_blocks_citation_coverage(self):
        import hashlib
        result = audit_claim_citations(
            claims=[{"text": "Claim.", "citations": [{
                "source_id": "src", "excerpt": "quote",
                "source_sha256": "0" * 64, "chunk_sha256": hashlib.sha256(b"quote").hexdigest(),
                "chunk_text": "quote", "chunk_index": 0,
                "source_start_char": 0, "source_end_char": 5,
                "excerpt_start_char": 0, "excerpt_end_char": 5,
            }]}],
            source_registry=[{"source_id": "src", "text": "quote"}],
        )
        citation = result["claims"][0]["citations"][0]
        self.assertEqual(citation["status"], "provenance_mismatch")
        self.assertFalse(citation["chunk_provenance_verified"])
        self.assertEqual(result["metrics"]["claims_without_valid_citations"], 1)


    def test_partial_chunk_provenance_cannot_pass_as_plain_excerpt_match(self):
        import hashlib
        source_text = "context exact excerpt tail"
        result = audit_claim_citations(
            claims=[{"text": "Claim.", "citations": [{
                "source_id": "src",
                "excerpt": "exact excerpt",
                "chunk_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
            }]}],
            source_registry=[{"source_id": "src", "text": source_text}],
        )
        citation = result["claims"][0]["citations"][0]
        self.assertEqual(citation["status"], "provenance_mismatch")
        self.assertFalse(citation["source_text_match"])
        self.assertFalse(citation["chunk_provenance_verified"])
        self.assertEqual(result["status"], "needs_review")

    def test_boolean_excerpt_offsets_are_rejected_as_provenance(self):
        import hashlib
        source_text = "exact excerpt"
        source_hash = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        result = audit_claim_citations(
            claims=[{"text": "Claim.", "citations": [{
                "source_id": "src", "excerpt": "exact excerpt",
                "source_sha256": source_hash, "chunk_sha256": source_hash,
                "chunk_text": source_text, "chunk_index": 0,
                "source_start_char": 0, "source_end_char": len(source_text),
                "excerpt_start_char": False, "excerpt_end_char": len(source_text),
            }]}],
            source_registry=[{"source_id": "src", "text": source_text}],
        )
        citation = result["claims"][0]["citations"][0]
        self.assertEqual(citation["status"], "provenance_mismatch")
        self.assertFalse(citation["chunk_provenance_verified"])
        self.assertEqual(result["metrics"]["claims_without_valid_citations"], 1)



if __name__ == "__main__":
    unittest.main()
