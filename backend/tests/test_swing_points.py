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

    def test_confirmed_swings_are_prefix_stable(self):
        bars = [
            {"high": high, "low": low, "timestamp": f"t{i}"}
            for i, (high, low) in enumerate([
                (10, 8), (12, 7), (11, 6), (9, 7), (8, 8),
                (13, 5), (10, 6), (9, 7), (8, 8), (7, 9),
            ])
        ]
        full = find_swing_points(bars, left=1, right=2)
        for end in range(4, len(bars) + 1):
            prefix = find_swing_points(bars[:end], left=1, right=2)
            for key in ("confirmed_swing_highs", "confirmed_swing_lows"):
                expected = [
                    point for point in full[key]
                    if point["confirmation_index"] < end
                ]
                self.assertEqual(prefix[key], expected, msg=f"{key} differs at prefix {end}")

    def test_edges_are_not_labelled_without_confirmation(self):
        bars = [{"high": 10, "low": 8} for _ in range(4)]
        result = find_swing_points(bars, 1, 1)
        self.assertEqual(result["confirmed_swing_highs"], [])
        self.assertEqual(result["confirmed_swing_lows"], [])

    def test_window_must_be_positive_integer_not_bool_or_float(self):
        for left, right in ((1.5, 1), (1, 2.5), (True, 1), (1, False), (0, 1), (1, -1)):
            with self.subTest(left=left, right=right):
                with self.assertRaisesRegex(ValueError, "positive integers"):
                    find_swing_points([], left=left, right=right)

    def test_rejects_nonfinite_or_invalid_bar_prices(self):
        for invalid in (float("nan"), float("inf"), True, "12"):
            with self.subTest(invalid=invalid):
                bars = [{"high": invalid, "low": 1}] * 5
                with self.assertRaises(ValueError):
                    find_swing_points(bars, left=1, right=1)
        with self.assertRaisesRegex(ValueError, "low must be <= high"):
            find_swing_points([{"high": 2, "low": 3}] * 5, left=1, right=1)

    def test_bars_must_be_a_sequence_of_objects(self):
        with self.assertRaisesRegex(ValueError, "list or tuple"):
            find_swing_points("not bars")
        with self.assertRaisesRegex(ValueError, "must be an object"):
            find_swing_points([None])
    def test_window_must_be_positive_integer_not_bool_or_float(self):
        for left, right in ((True, 1), (1, False), (1.5, 1), (1, 2.5), (-1, 1)):
            with self.subTest(left=left, right=right):
                with self.assertRaises(ValueError):
                    find_swing_points([], left, right)

    def test_invalid_prices_rejected(self):
        for field, value in (("high", float("inf")), ("low", float("nan")), ("high", True)):
            bars = [{"high": 10, "low": 8}, {"high": 11, "low": 7}]
            bars[0][field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    find_swing_points(bars, 1, 1)

    def test_low_cannot_exceed_high(self):
        bars = [{"high": 8, "low": 9}, {"high": 10, "low": 7}]
        with self.assertRaisesRegex(ValueError, "low must be <= high"):
            find_swing_points(bars, 1, 1)

    def test_invalid_window_rejected(self):
        with self.assertRaises(ValueError):
            find_swing_points([], 0, 1)


if __name__ == "__main__":
    unittest.main()
