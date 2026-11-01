import unittest

from app.liquidity_indicators import calculate_volume_profile


class LiquidityIndicatorTests(unittest.TestCase):
    def test_volume_profile_returns_poc_and_value_area(self):
        report = calculate_volume_profile(
            high=[10, 11, 12, 13], low=[8, 9, 10, 11],
            close=[9, 10, 11, 12], volume=[10, 30, 50, 10],
            bins=4, value_area_pct=70,
        )
        self.assertEqual(len(report["profile"]), 4)
        self.assertIsNotNone(report["poc"])
        self.assertGreaterEqual(report["value_area_high"], report["value_area_low"])
        self.assertEqual(report["total_volume"], 100)
        self.assertTrue(report["metadata"]["classification"].startswith("ohlcv_approximation"))

    def test_flat_price_profile_is_supported(self):
        report = calculate_volume_profile(
            high=[10, 10], low=[10, 10], close=[10, 10], volume=[2, 3]
        )
        self.assertEqual(len(report["profile"]), 1)
        self.assertEqual(report["total_volume"], 5)
        self.assertEqual(report["poc"], 10)

    def test_invalid_parameters_are_rejected(self):
        base = dict(high=[10, 11], low=[9, 10], close=[9.5, 10.5], volume=[1, 2])
        for kwargs in ({"bins": 1}, {"bins": 501}, {"value_area_pct": 0}, {"value_area_pct": 101}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    calculate_volume_profile(**base, **kwargs)

    def test_invalid_ohlcv_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_volume_profile(
                high=[8, 9], low=[9, 8], close=[8, 8.5], volume=[1, 2]
            )


if __name__ == "__main__":
    unittest.main()
