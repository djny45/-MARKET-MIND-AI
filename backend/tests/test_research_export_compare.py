import unittest

from app.research_export_compare import compare_research_exports


def bundle(observations, **extra):
    result = {
        "report_type": "historical_research_evidence",
        "scope": {"symbol": "BTCUSD", "interval": "1h", "source": "alpha"},
        "observations": observations,
        "data_quality": {"gap_count": 0},
        "integrity": {"digest": "abc"},
    }
    result.update(extra)
    return result


class ResearchExportCompareTests(unittest.TestCase):
    def test_reports_added_removed_and_changed_observations(self):
        before = bundle([
            {"timestamp": "2026-01-01T00:00:00Z", "source": "alpha", "close": 10},
            {"timestamp": "2026-01-01T01:00:00Z", "source": "alpha", "close": 11},
        ])
        after = bundle([
            {"timestamp": "2026-01-01T00:00:00Z", "source": "alpha", "close": 12},
            {"timestamp": "2026-01-01T02:00:00Z", "source": "alpha", "close": 13},
        ])
        result = compare_research_exports(before, after)
        self.assertEqual(result["counts"]["added"], 1)
        self.assertEqual(result["counts"]["removed"], 1)
        self.assertEqual(result["counts"]["changed"], 1)
        self.assertEqual(result["changed"][0]["fields"], ["close"])

    def test_reports_diagnostic_and_provenance_changes(self):
        before = bundle([], data_quality={"gap_count": 0})
        after = bundle([], data_quality={"gap_count": 2})
        after["scope"]["source"] = "beta"
        result = compare_research_exports(before, after)
        self.assertEqual(result["diagnostic_changed_paths"]["data_quality"], ["gap_count"])
        self.assertEqual(result["provenance_changed_fields"], ["source"])

    def test_source_sha256_change_is_reported_as_provenance(self):
        before = bundle([])
        after = bundle([])
        before["scope"]["source_sha256"] = "a" * 64
        after["scope"]["source_sha256"] = "b" * 64
        result = compare_research_exports(before, after)
        self.assertIn("source_sha256", result["provenance_changed_fields"])

    def test_integrity_digest_summary_omits_non_string_digest(self):
        before = bundle([], integrity={"digest": 123})
        after = bundle([], integrity={"digest": None})
        result = compare_research_exports(before, after)
        self.assertIsNone(result["integrity_digests"]["before"])
        self.assertIsNone(result["integrity_digests"]["after"])

    def test_duplicate_and_malformed_keys_are_counted(self):
        row = {"timestamp": "2026-01-01T00:00:00Z", "source": "alpha", "close": 10}
        before = bundle([row, row, {"close": 11}])
        after = bundle([row])
        result = compare_research_exports(before, after)
        self.assertEqual(result["counts"]["invalid_or_duplicate_keys"]["before"], 2)

    def test_rejects_non_list_observations(self):
        before = bundle([])
        after = bundle([])
        after["observations"] = {"timestamp": "2026-01-01T00:00:00Z"}
        with self.assertRaisesRegex(ValueError, "observations_must_be_a_list"):
            compare_research_exports(before, after)

    def test_rejects_non_object_scope(self):
        before = bundle([])
        after = bundle([])
        after["scope"] = ["BTCUSD", "1h"]
        with self.assertRaisesRegex(ValueError, "export_scope_must_be_an_object"):
            compare_research_exports(before, after)

    def test_reports_per_observation_provenance_changes(self):
        before = bundle([{"timestamp": "2026-01-01T00:00:00Z", "source": "alpha",
                          "status": "historical", "retrieved_at": "2026-01-02T00:00:00Z"}])
        after = bundle([{"timestamp": "2026-01-01T00:00:00Z", "source": "alpha",
                         "status": "delayed", "retrieved_at": "2026-01-03T00:00:00Z"}])
        result = compare_research_exports(before, after)
        self.assertEqual(result["changed"][0]["fields"], ["retrieved_at", "status"])

    def test_integrity_validation_detects_tampered_bundle(self):
        import hashlib
        import json
        before = bundle([])
        after = bundle([])
        for item in (before, after):
            payload = dict(item)
            payload.pop("integrity", None)
            canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
            item["integrity"] = {
                "algorithm": "sha256",
                "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                "scope": "complete evidence bundle excluding this integrity field",
                "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
            }
        after["observations"].append({"timestamp": "2026-01-01T00:00:00Z", "source": "csv"})
        result = compare_research_exports(before, after)
        self.assertTrue(result["integrity_validation"]["before"]["valid"])
        self.assertFalse(result["integrity_validation"]["after"]["valid"])
        self.assertEqual(result["integrity_validation"]["after"]["reason"], "digest_mismatch")

    def test_malformed_integrity_metadata_does_not_crash_digest_summary(self):
        before = bundle([], integrity="malformed")
        after = bundle([], integrity=["not", "an", "object"])
        result = compare_research_exports(before, after)
        self.assertIsNone(result["integrity_digests"]["before"])
        self.assertIsNone(result["integrity_digests"]["after"])
        self.assertEqual(result["integrity_validation"]["before"]["reason"], "integrity_metadata_missing")
        self.assertEqual(result["integrity_validation"]["after"]["reason"], "integrity_metadata_missing")


    def test_integrity_validation_detects_provenance_tampering(self):
        import hashlib
        import json

        original = bundle([])
        payload = dict(original)
        payload.pop("integrity", None)
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        original["integrity"] = {
            "algorithm": "sha256",
            "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "scope": "complete evidence bundle excluding this integrity field",
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
        }
        altered = json.loads(json.dumps(original))
        altered["scope"]["source_sha256"] = "f" * 64

        result = compare_research_exports(original, altered)
        self.assertTrue(result["integrity_validation"]["before"]["valid"])
        self.assertFalse(result["integrity_validation"]["after"]["valid"])
        self.assertEqual(
            result["integrity_validation"]["after"]["reason"], "digest_mismatch"
        )

    def test_integrity_validation_rejects_malformed_digest_and_metadata(self):
        before = bundle([])
        after = bundle([])
        before["integrity"] = {
            "algorithm": "sha256",
            "digest": "g" * 64,
            "scope": "complete evidence bundle excluding this integrity field",
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
        }
        after["integrity"] = {
            "algorithm": "sha1",
            "digest": "a" * 64,
            "scope": "complete evidence bundle excluding this integrity field",
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
        }

        result = compare_research_exports(before, after)
        self.assertEqual(
            result["integrity_validation"]["before"]["reason"],
            "invalid_digest_format",
        )
        self.assertEqual(
            result["integrity_validation"]["after"]["reason"],
            "unsupported_integrity_algorithm",
        )

    def test_rejects_different_symbol_or_interval(self):
        before = bundle([])
        after = bundle([])
        after["scope"]["symbol"] = "ETHUSD"
        with self.assertRaises(ValueError):
            compare_research_exports(before, after)


    def test_integrity_validation_accepts_uppercase_sha256_digest(self):
        import hashlib
        import json

        item = bundle([])
        payload = dict(item)
        payload.pop("integrity", None)
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        item["integrity"] = {
            "algorithm": "sha256",
            "digest": digest.upper(),
            "scope": "complete evidence bundle excluding this integrity field",
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
        }

        result = compare_research_exports(item, item)
        self.assertTrue(result["integrity_validation"]["before"]["valid"])
        self.assertEqual(
            result["integrity_validation"]["before"]["expected_digest"], digest
        )

    def test_integrity_validation_rejects_non_finite_json_values(self):
        import hashlib
        import json

        item = bundle([])
        payload = dict(item)
        payload.pop("integrity", None)
        canonical = json.dumps(
            payload, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        item["integrity"] = {
            "algorithm": "sha256",
            "digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            "scope": "complete evidence bundle excluding this integrity field",
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
        }
        item["data_quality"]["unexpected_value"] = float("nan")

        result = compare_research_exports(item, item)
        self.assertFalse(result["integrity_validation"]["before"]["valid"])
        self.assertEqual(
            result["integrity_validation"]["before"]["reason"],
            "bundle_cannot_be_canonicalized",
        )


    def test_integrity_validation_reports_unsupported_scope_and_canonicalization(self):
        before = bundle([])
        after = bundle([])
        valid_metadata = {
            "algorithm": "sha256",
            "digest": "a" * 64,
            "scope": "complete evidence bundle excluding this integrity field",
            "canonicalization": "UTF-8 JSON with sorted keys and compact separators",
        }
        before["integrity"] = dict(valid_metadata, scope="observations only")
        after["integrity"] = dict(
            valid_metadata, canonicalization="JSON with default separators"
        )

        result = compare_research_exports(before, after)
        self.assertEqual(
            result["integrity_validation"]["before"]["reason"],
            "unsupported_integrity_scope",
        )
        self.assertEqual(
            result["integrity_validation"]["after"]["reason"],
            "unsupported_canonicalization",
        )


    def test_empty_timestamp_or_source_is_counted_as_invalid_key(self):
        before = bundle([
            {"timestamp": "", "source": "alpha", "close": 10},
            {"timestamp": "2026-01-01T00:00:00Z", "source": "   ", "close": 11},
            {"timestamp": "2026-01-01T01:00:00Z", "source": "alpha", "close": 12},
        ])
        after = bundle([
            {"timestamp": "2026-01-01T01:00:00Z", "source": "alpha", "close": 12},
        ])

        result = compare_research_exports(before, after)
        self.assertEqual(
            result["counts"]["invalid_or_duplicate_keys"]["before"], 2
        )
        self.assertEqual(result["counts"]["unchanged"], 1)


    def test_rejects_missing_or_blank_symbol_and_interval_on_either_input(self):
        for side in ("before", "after"):
            for field in ("symbol", "interval"):
                for invalid_value in (None, "", "   "):
                    before = bundle([])
                    after = bundle([])
                    target = before if side == "before" else after
                    target["scope"][field] = invalid_value
                    with self.subTest(side=side, field=field, value=invalid_value):
                        with self.assertRaisesRegex(
                            ValueError, "export_scope_symbol_and_interval_required"
                        ):
                            compare_research_exports(before, after)


    def test_rejects_interval_scope_mismatch(self):
        before = bundle([])
        after = bundle([])
        after["scope"]["interval"] = "4h"
        with self.assertRaisesRegex(ValueError, "export_scope_mismatch"):
            compare_research_exports(before, after)

    def test_rejects_non_string_symbol_and_interval(self):
        for field, invalid_value in (("symbol", 123), ("interval", ["1h"])):
            before = bundle([])
            after = bundle([])
            before["scope"][field] = invalid_value
            with self.subTest(field=field, value=invalid_value):
                with self.assertRaisesRegex(
                    ValueError, "export_scope_symbol_and_interval_required"
                ):
                    compare_research_exports(before, after)

    def test_mixed_type_observation_fields_compare_without_sort_error(self):
        before = bundle([{"timestamp": "t1", "source": "csv", "close": 10, 7: "legacy"}])
        after = bundle([{"timestamp": "t1", "source": "csv", "close": 10, "extra": 1}])
        result = compare_research_exports(before, after)
        self.assertEqual(result["counts"]["changed"], 1)

    def test_mixed_type_diagnostic_keys_compare_without_sort_error(self):
        before = bundle([], data_quality={"gap_count": 0, 7: "legacy"})
        after = bundle([], data_quality={"gap_count": 1, "other": True})
        result = compare_research_exports(before, after)
        self.assertIn("data_quality", result["diagnostic_changed_paths"])

    def test_colliding_stringified_field_keys_have_stable_order(self):
        before = bundle([{"timestamp": "t1", "source": "csv", 1: "old", "1": "old"}])
        after = bundle([{"timestamp": "t1", "source": "csv", 1: "new", "1": "new"}])
        result = compare_research_exports(before, after)
        self.assertEqual(result["changed"][0]["fields"], [1, "1"])


if __name__ == "__main__":
    unittest.main()
