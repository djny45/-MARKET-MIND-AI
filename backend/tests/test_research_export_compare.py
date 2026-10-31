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

    def test_rejects_different_symbol_or_interval(self):
        before = bundle([])
        after = bundle([])
        after["scope"]["symbol"] = "ETHUSD"
        with self.assertRaises(ValueError):
            compare_research_exports(before, after)


if __name__ == "__main__":
    unittest.main()
