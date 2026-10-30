import hashlib
import json
import unittest

from app.research_export import build_research_evidence_bundle


class ResearchEvidenceBundleTests(unittest.TestCase):
    def test_bundle_preserves_observations_provenance_and_diagnostics(self):
        bars = [
            {"timestamp": "2026-01-01T00:00:00Z", "source": "alpha", "status": "historical",
             "retrieved_at": "2026-01-02T00:00:00Z", "open": 10, "high": 12, "low": 9,
             "close": 11, "volume": 100},
            {"timestamp": "2026-01-01T00:00:00+00:00", "source": "beta", "status": "historical",
             "retrieved_at": "2026-01-02T01:00:00Z", "open": 10, "high": 12, "low": 9,
             "close": 11.5, "volume": 110},
        ]
        history = {"symbol": "btcusd", "interval": "1h", "bars": bars,
                   "source": "mixed", "sources": ["alpha", "beta"], "status": "historical",
                   "retrieved_at": "2026-01-02T01:00:00Z",
                   "first_timestamp": bars[0]["timestamp"], "last_timestamp": bars[1]["timestamp"]}
        bundle = build_research_evidence_bundle("btcusd", "1h", history, {"status": "available"})
        self.assertEqual(bundle["schema_version"], "1.1")
        integrity = bundle.pop("integrity")
        canonical = json.dumps(bundle, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        expected_digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        self.assertEqual(integrity["algorithm"], "sha256")
        self.assertEqual(integrity["digest"], expected_digest)
        bundle["integrity"] = integrity
        self.assertEqual(bundle["scope"]["symbol"], "BTCUSD")
        self.assertEqual(bundle["observations"], bars)
        self.assertEqual(bundle["source_comparison"]["shared_timestamp_count"], 1)
        self.assertEqual(bundle["source_comparison"]["comparisons"][0]["source_count"], 2)
        self.assertEqual(bundle["deep_research"], {"status": "available"})
        self.assertTrue(any("No forecasts" in item for item in bundle["limitations"]))

    def test_empty_history_is_exportable_without_fabricated_observations(self):
        bundle = build_research_evidence_bundle("ETHUSD", "1h", {"bars": [], "sources": []})
        self.assertEqual(bundle["observations"], [])
        self.assertEqual(bundle["scope"]["observation_count"], 0)
        self.assertEqual(bundle["source_comparison"]["shared_timestamp_count"], 0)


if __name__ == "__main__":
    unittest.main()
