import json
import unittest

from app.historical_integrity import build_historical_integrity_matrix


def bar(source="alpha", timestamp="2026-01-01T00:00:00Z"):
    return {
        "timestamp": timestamp, "source": source, "status": "historical",
        "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100,
    }


class HistoricalIntegrityTests(unittest.TestCase):
    def test_source_counts_and_shared_utc_instants(self):
        result = build_historical_integrity_matrix({"symbol": "TEST", "interval": "1h", "bars": [
            bar("alpha"), bar("beta", "2026-01-01T01:00:00+01:00"),
            bar("alpha", "2026-01-01T01:00:00Z"),
        ]})
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["shared_utc_timestamp_count"], 1)
        self.assertEqual(result["sources"]["alpha"]["duplicate_utc_timestamp_count"], 0)
        self.assertEqual(result["sources"]["alpha"]["timestamp_coverage_pct"], 100)

    def test_same_source_timezone_duplicate_is_counted(self):
        result = build_historical_integrity_matrix({"bars": [
            bar("alpha"), bar("alpha", "2026-01-01T01:00:00+01:00")
        ]})
        self.assertEqual(result["sources"]["alpha"]["duplicate_utc_timestamp_count"], 1)

    def test_missing_malformed_and_non_finite_fields_are_separate(self):
        bad = bar("alpha")
        bad.pop("open")
        bad["high"] = float("inf")
        bad["low"] = "not-numeric"
        result = build_historical_integrity_matrix({"bars": [bad]})
        source = result["sources"]["alpha"]
        self.assertEqual(source["missing_field_counts"]["open"], 1)
        self.assertEqual(source["invalid_numeric_field_counts"]["high"], 1)
        self.assertEqual(source["invalid_numeric_field_counts"]["low"], 1)
        self.assertEqual(source["valid_numeric_field_counts"]["close"], 1)
        json.dumps(result, allow_nan=False)

    def test_invalid_ohlcv_relationships_are_flagged(self):
        bad = bar()
        bad["high"] = 10.5
        bad["low"] = 11.5
        bad["volume"] = -1
        result = build_historical_integrity_matrix({"bars": [bad]})
        source = result["sources"]["alpha"]
        self.assertEqual(source["invalid_ohlcv_structure_count"], 1)
        self.assertEqual(len(source["invalid_ohlcv_examples"]), 1)

    def test_naive_timestamp_is_not_treated_as_valid_utc(self):
        result = build_historical_integrity_matrix({"bars": [bar(timestamp="2026-01-01T00:00:00")]})
        source = result["sources"]["alpha"]
        self.assertEqual(source["invalid_timestamp_count"], 1)
        self.assertEqual(source["timestamp_coverage_pct"], 0)

    def test_no_single_composite_score_is_created(self):
        result = build_historical_integrity_matrix({"bars": [bar()]})
        self.assertNotIn("quality_score", result)
        self.assertIn("No composite quality score", result["methodology"][-2])


if __name__ == "__main__":
    unittest.main()
