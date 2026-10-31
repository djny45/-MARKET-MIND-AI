import hashlib
import json
import unittest

from verify_research_export import build_verification_report, verify_bundle


def signed_bundle():
    payload = {
        "schema_version": "1.1",
        "report_type": "historical_research_evidence",
        "scope": {"symbol": "BTCUSD"},
        "observations": [{"close": 100.5, "source": "user-csv"}],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    payload["integrity"] = {
        "algorithm": "sha256",
        "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    }
    return payload


class VerifyResearchExportTests(unittest.TestCase):
    def test_builds_detached_report_with_file_hash_and_timestamp(self):
        raw = b'{"schema_version":"1.1"}'
        result = {"valid": True, "reason": "digest_matches"}
        report = build_verification_report(
            "sample-research.json", raw, result, "2026-10-31T10:00:00+00:00"
        )
        self.assertEqual(report["file_name"], "sample-research.json")
        self.assertEqual(report["file_size_bytes"], len(raw))
        self.assertEqual(report["file_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(report["verified_at_utc"], "2026-10-31T10:00:00+00:00")
        self.assertEqual(report["verification"], result)

    def test_accepts_unchanged_export(self):
        result = verify_bundle(signed_bundle())
        self.assertTrue(result["valid"])
        self.assertEqual(result["reason"], "digest_matches")

    def test_detects_modified_observation(self):
        bundle = signed_bundle()
        bundle["observations"][0]["close"] = 101.5
        result = verify_bundle(bundle)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "digest_mismatch")

    def test_detects_modified_provenance(self):
        bundle = signed_bundle()
        bundle["observations"][0]["source"] = "different-source"
        result = verify_bundle(bundle)
        self.assertFalse(result["valid"])
        self.assertEqual(result["reason"], "digest_mismatch")

    def test_rejects_missing_or_unsupported_integrity_metadata(self):
        self.assertEqual(verify_bundle({})["reason"], "integrity_metadata_missing")
        bundle = signed_bundle()
        bundle["integrity"]["algorithm"] = "md5"
        self.assertEqual(verify_bundle(bundle)["reason"], "unsupported_integrity_algorithm")

    def test_rejects_malformed_digest_and_non_object_payload(self):
        bundle = signed_bundle()
        bundle["integrity"]["digest"] = "not-a-digest"
        self.assertEqual(verify_bundle(bundle)["reason"], "invalid_digest_format")
        self.assertEqual(verify_bundle([])["reason"], "top_level_json_must_be_an_object")


if __name__ == "__main__":
    unittest.main()
