import unittest

from app.swing_points import find_swing_points


class SwingPointTests(unittest.TestCase):
    def test_finds_confirmed_high_and_low(self):
        bars = [
            {"high": 10, "low": 8, "timestamp": "a"},
            {"high": 12, "low": 7, "timestamp": "b"},
            {"high": 11, "low": 6, "timestamp": "c"},
            {"high": 9, "low": 7, "timestamp": "d"},
            {"high": 8, "low": 8, "timestamp": "e"},
        ]
        result = find_swing_points(bars, 1, 1)
        self.assertEqual(result["confirmed_swing_highs"][0]["index"], 1)
        self.assertEqual(result["confirmed_swing_lows"][0]["index"], 2)

    def test_swing_reports_confirmation_index_and_timestamp(self):
        bars = [
            {"high": 10, "low": 8, "timestamp": "t0"},
            {"high": 12, "low": 7, "timestamp": "t1"},
            {"high": 11, "low": 6, "timestamp": "t2"},
            {"high": 9, "low": 7, "timestamp": "t3"},
            {"high": 8, "low": 8, "timestamp": "t4"},
        ]
        result = find_swing_points(bars, 1, 1)
        swing = result["confirmed_swing_highs"][0]
        self.assertEqual(swing["index"], 1)
        self.assertEqual(swing["timestamp"], "t1")
        self.assertEqual(swing["confirmation_index"], 2)
        self.assertEqual(swing["confirmation_timestamp"], "t2")

    def test_edges_are_not_labelled_without_confirmation(self):
        bars = [{"high": 10, "low": 8} for _ in range(4)]
        result = find_swing_points(bars, 1, 1)
        self.assertEqual(result["confirmed_swing_highs"], [])
        self.assertEqual(result["confirmed_swing_lows"], [])

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            find_swing_points([], 0, 1)


if __name__ == "__main__":
    unittest.main()
