import unittest

from app.correlation import build_correlation_report


def history(values):
    return {"bars": [
        {"timestamp": f"2026-01-{i + 1:02d}T00:00:00+00:00", "close": value}
        for i, value in enumerate(values)
    ]}


class CorrelationTests(unittest.TestCase):
    def test_perfect_positive_relationship(self):
        result = build_correlation_report({
            "AAA": history([10, 11, 12, 13, 14]),
            "BBB": history([20, 22, 24, 26, 28]),
        })
        self.assertEqual(result["pearson_return_correlation"]["AAA"]["BBB"], 1.0)

    def test_unmatched_timestamps_are_excluded(self):
        left = history([10, 11, 12, 13])
        right = history([20, 21, 22, 23])
        right["bars"][-1]["timestamp"] = "2026-02-01T00:00:00+00:00"
        result = build_correlation_report({"A": left, "B": right})
        self.assertLess(result["paired_return_observations"]["A"]["B"], 3)

    def test_constant_series_returns_null(self):
        result = build_correlation_report({
            "A": history([10, 10, 10, 10]),
            "B": history([10, 11, 12, 13]),
        })
        self.assertIsNone(result["pearson_return_correlation"]["A"]["B"])

    def test_requires_two_symbols(self):
        with self.assertRaises(ValueError):
            build_correlation_report({"A": history([1, 2, 3])})


if __name__ == "__main__":
    unittest.main()
