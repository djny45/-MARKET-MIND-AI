import unittest

from app.candle_patterns import classify_candles


class CandlePatternTests(unittest.TestCase):
    def test_doji_like(self):
        bars = [{"open": 10, "high": 12, "low": 8, "close": 10.1}]
        self.assertIn("doji_like", classify_candles(bars)[0]["patterns"])

    def test_bullish_engulfing_shape(self):
        bars = [
            {"open": 10, "high": 10.5, "low": 8.5, "close": 9},
            {"open": 8.8, "high": 11, "low": 8.5, "close": 10.8},
        ]
        self.assertIn("bullish_engulfing_shape", classify_candles(bars)[1]["patterns"])

    def test_inside_bar(self):
        bars = [
            {"open": 10, "high": 12, "low": 8, "close": 11},
            {"open": 10.2, "high": 11.5, "low": 8.5, "close": 10.7},
        ]
        self.assertIn("inside_bar", classify_candles(bars)[1]["patterns"])

    def test_flat_range_has_no_division_error(self):
        bars = [{"open": 10, "high": 10, "low": 10, "close": 10}]
        self.assertEqual(classify_candles(bars)[0]["patterns"], [])


if __name__ == "__main__":
    unittest.main()
