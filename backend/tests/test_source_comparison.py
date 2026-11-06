import unittest

from app.source_comparison import compare_source_observations


class SourceComparisonTests(unittest.TestCase):
    def bars(self):
        return [
            {"timestamp": "2026-01-01T00:00:00Z", "source": "provider-a", "status": "historical",
             "retrieved_at": "2026-01-02T00:00:00Z", "open": 100, "high": 105, "low": 99, "close": 103, "volume": 10},
            {"timestamp": "2026-01-01T01:00:00+01:00", "source": "provider-b", "status": "historical",
             "retrieved_at": "2026-01-02T01:00:00Z", "open": 100, "high": 106, "low": 99, "close": 104, "volume": 12},
            {"timestamp": "2026-01-01T01:00:00Z", "source": "provider-a", "status": "historical",
             "retrieved_at": "2026-01-02T00:00:00Z", "open": 103, "high": 108, "low": 102, "close": 107, "volume": 11},
        ]

    def test_compares_only_exact_utc_instants_and_retains_provenance(self):
        result = compare_source_observations({"symbol": "BTCUSD", "interval": "1h", "bars": self.bars()})
        self.assertEqual(result["shared_timestamp_count"], 1)
        comparison = result["comparisons"][0]
        self.assertEqual(comparison["source_count"], 2)
        self.assertEqual(comparison["field_ranges"]["close"]["absolute_spread"], 1)
        self.assertEqual(comparison["sources"]["provider-a"][0]["timestamp"], "2026-01-01T00:00:00Z")
        self.assertEqual(comparison["sources"]["provider-b"][0]["status"], "historical")

    def test_single_source_timestamp_is_not_reported_as_comparison(self):
        bars = self.bars()[:1]
        result = compare_source_observations({"symbol": "BTCUSD", "interval": "1h", "bars": bars})
        self.assertEqual(result["shared_timestamp_count"], 0)
        self.assertEqual(result["comparisons"], [])

    def test_invalid_timestamps_are_reported_not_compared(self):
        bars = self.bars()
        bars.append({"timestamp": "no-timezone", "source": "provider-c"})
        result = compare_source_observations({"symbol": "BTCUSD", "interval": "1h", "bars": bars})
        self.assertEqual(result["invalid_timestamp_count"], 1)
        self.assertEqual(result["invalid_timestamps"][0]["bar_index"], 3)

    def test_missing_and_malformed_numeric_values_do_not_break_ranges(self):
        bars = self.bars()
        bars[1]["close"] = "not-a-number"
        bars[0]["close"] = None
        bars.append({**bars[1], "source": "provider-c", "close": 105, "volume": 8})
        bars[1]["volume"] = float("nan")
        result = compare_source_observations({"symbol": "BTCUSD", "interval": "1h", "bars": bars})
        close = result["comparisons"][0]["field_ranges"]["close"]
        volume = result["comparisons"][0]["field_ranges"]["volume"]
        self.assertEqual(close["valid_value_count"], 1)
        self.assertEqual(close["missing_value_count"], 1)
        self.assertEqual(close["invalid_value_count"], 1)
        self.assertEqual(close["absolute_spread"], 0.0)
        self.assertEqual(volume["invalid_value_count"], 1)
        self.assertEqual(volume["valid_value_count"], 2)

    def test_extreme_finite_values_do_not_emit_infinite_spread(self):
        bars = [
            {"timestamp": "2026-01-01T00:00:00Z", "source": "provider-a",
             "open": 1, "high": 1, "low": 1, "close": -1e308, "volume": 0},
            {"timestamp": "2026-01-01T00:00:00Z", "source": "provider-b",
             "open": 1, "high": 1, "low": 1, "close": 1e308, "volume": 0},
        ]
        result = compare_source_observations({"bars": bars})
        close = result["comparisons"][0]["field_ranges"]["close"]
        self.assertIsNone(close["absolute_spread"])
        self.assertEqual(close["spread_status"], "unavailable_nonfinite_spread")

    def test_same_source_duplicate_instant_is_reported(self):
        bars = self.bars()
        bars.append({**bars[0], "timestamp": "2026-01-01T01:00:00Z", "close": 106})
        bars.append({**bars[1], "timestamp": "2026-01-01T01:00:00Z", "source": "provider-b", "close": 105})
        result = compare_source_observations({"symbol": "BTCUSD", "interval": "1h", "bars": bars})
        later = next(item for item in result["comparisons"] if item["timestamp_utc"].startswith("2026-01-01T01:00"))
        self.assertEqual(later["same_source_duplicate_count"], 1)


if __name__ == "__main__":
    unittest.main()
