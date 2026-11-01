import unittest

from app.volume_indicators import calculate_volume_indicators


class VolumeIndicatorTests(unittest.TestCase):
    def setUp(self):
        self.high = [10, 11, 12, 11, 13, 14, 13, 15]
        self.low = [8, 9, 10, 9, 11, 12, 11, 13]
        self.close = [9, 10, 11, 10, 12, 13, 12, 14]
        self.volume = [100, 120, 150, 90, 180, 200, 160, 220]

    def test_returns_all_volume_series(self):
        result = calculate_volume_indicators(
            self.high, self.low, self.close, self.volume, period=3
        )
        expected = {
            "obv", "adl", "chaikin_oscillator", "cmf", "mfi",
            "force_index", "ease_of_movement", "vpt", "nvi", "pvi",
            "vwap", "relative_volume", "volume_oscillator",
            "volume_rate_of_change", "volume_sma", "metadata",
        }
        self.assertEqual(set(result), expected)
        for key in expected - {"metadata"}:
            self.assertEqual(len(result[key]), len(self.close), key)

    def test_vwap_is_volume_weighted_typical_price(self):
        result = calculate_volume_indicators(
            self.high, self.low, self.close, self.volume, period=3
        )
        typical = [(h+l+c)/3 for h,l,c in zip(self.high,self.low,self.close)]
        expected = sum(p*v for p,v in zip(typical,self.volume))/sum(self.volume)
        self.assertAlmostEqual(result["vwap"][-1], expected)

    def test_rejects_mismatched_lengths(self):
        with self.assertRaises(ValueError):
            calculate_volume_indicators(self.high, self.low, self.close, self.volume[:-1])

    def test_rejects_negative_volume(self):
        bad = self.volume.copy()
        bad[2] = -1
        with self.assertRaises(ValueError):
            calculate_volume_indicators(self.high, self.low, self.close, bad)

    def test_rejects_inconsistent_ohlc(self):
        bad_high = self.high.copy()
        bad_high[0] = 7
        with self.assertRaises(ValueError):
            calculate_volume_indicators(bad_high, self.low, self.close, self.volume)


if __name__ == "__main__":
    unittest.main()
