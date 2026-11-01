import unittest

from app.cross_market_correlation import build_cross_market_correlation


def history(closes, timestamps=None, source="csv", status="historical"):
    timestamps = timestamps or [f"2026-01-{i:02d}T00:00:00+00:00" for i in range(1, len(closes) + 1)]
    return {"bars": [
        {"timestamp": stamp, "close": close, "source": source, "status": status}
        for stamp, close in zip(timestamps, closes)
    ]}


class CrossMarketCorrelationTests(unittest.TestCase):
    def test_perfect_positive_return_correlation_on_exact_utc_overlap(self):
        result = build_cross_market_correlation({
            "india:nse:A": history([100, 110, 99, 108.9]),
            "us:nyse:B": history([50, 55, 49.5, 54.45]),
        }, "1d", min_observations=3)
        pair = result["pairs"][0]
        self.assertEqual(pair["status"], "available")
        self.assertAlmostEqual(pair["correlation"], 1.0)
        self.assertEqual(pair["return_observations"], 3)

    def test_timezone_offsets_normalize_to_same_utc_instants(self):
        result = build_cross_market_correlation({
            "A": history([10, 11, 12], [
                "2026-01-01T05:30:00+05:30", "2026-01-02T05:30:00+05:30", "2026-01-03T05:30:00+05:30"
            ]),
            "B": history([20, 22, 24], [
                "2026-01-01T00:00:00Z", "2026-01-02T00:00:00Z", "2026-01-03T00:00:00Z"
            ]),
        }, "1d", min_observations=2)
        self.assertEqual(result["pairs"][0]["aligned_bar_count"], 3)
        self.assertAlmostEqual(result["pairs"][0]["correlation"], 1.0)

    def test_missing_sessions_use_intersection_without_forward_fill(self):
        result = build_cross_market_correlation({
            "A": history([100, 110, 121, 133.1]),
            "B": history([50, 55], [
                "2026-01-01T00:00:00Z", "2026-01-03T00:00:00Z"
            ]),
        }, "1d", min_observations=3)
        pair = result["pairs"][0]
        self.assertEqual(pair["aligned_bar_count"], 2)
        self.assertEqual(pair["status"], "insufficient_overlap")
        self.assertIsNone(pair["correlation"])

    def test_constant_returns_have_undefined_correlation(self):
        result = build_cross_market_correlation({
            "A": history([100, 100, 100, 100]),
            "B": history([100, 101, 102, 103]),
        }, "1d", min_observations=3)
        self.assertIsNone(result["pairs"][0]["correlation"])

    def test_rejects_naive_and_duplicate_timestamps(self):
        with self.assertRaises(ValueError):
            build_cross_market_correlation({
                "A": history([1, 2], ["2026-01-01T00:00:00", "2026-01-02T00:00:00Z"]),
                "B": history([1, 2]),
            }, "1d")
        with self.assertRaises(ValueError):
            build_cross_market_correlation({
                "A": history([1, 2], ["2026-01-01T00:00:00Z"] * 2),
                "B": history([1, 2]),
            }, "1d")

    def test_rejects_insufficient_instrument_count_and_invalid_threshold(self):
        with self.assertRaises(ValueError):
            build_cross_market_correlation({"A": history([1, 2])}, "1d")
        with self.assertRaises(ValueError):
            build_cross_market_correlation({"A": history([1, 2]), "B": history([1, 2])}, "1d", 2)


if __name__ == "__main__":
    unittest.main()
