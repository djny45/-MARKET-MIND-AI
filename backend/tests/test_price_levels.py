import unittest

from app.price_levels import build_price_level_clusters


class PriceLevelClusterTests(unittest.TestCase):
    def test_clusters_repeated_confirmed_swing_highs(self):
        highs = [10, 12, 10, 11, 10, 12.04, 10]
        lows = [9, 9, 9, 9, 9, 9, 9]
        bars = [{"high": h, "low": l, "timestamp": str(i)} for i, (h, l) in enumerate(zip(highs, lows))]
        result = build_price_level_clusters(bars, tolerance_pct=1, left=1, right=1)
        clusters = result["clusters"]["historical_swing_high"]
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["touch_count"], 2)

    def test_no_cluster_for_single_touch(self):
        bars = [{"high": h, "low": h - 1} for h in [10, 12, 10, 11, 10]]
        result = build_price_level_clusters(bars, left=1, right=1)
        self.assertEqual(result["clusters"]["historical_swing_high"], [])

    def test_invalid_parameters_rejected(self):
        with self.assertRaises(ValueError):
            build_price_level_clusters([], tolerance_pct=0)
        with self.assertRaises(ValueError):
            build_price_level_clusters([], min_touches=1)


if __name__ == "__main__":
    unittest.main()
