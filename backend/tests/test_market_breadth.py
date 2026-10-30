import unittest

from app.market_breadth import build_market_breadth_report


def history(values, timestamps=None):
    timestamps = timestamps or [
        f"2026-01-{index + 1:02d}T00:00:00+00:00"
        for index in range(len(values))
    ]
    return {"bars": [
        {"timestamp": timestamp, "close": value}
        for timestamp, value in zip(timestamps, values)
    ]}


class MarketBreadthTests(unittest.TestCase):
    def test_counts_advances_declines_and_unchanged(self):
        result = build_market_breadth_report({
            "AAA": history([10, 11, 11]),
            "BBB": history([20, 19, 20]),
            "CCC": history([30, 31, 31]),
        })
        first, second = result["observations"]
        self.assertEqual((first["advancing"], first["declining"], first["unchanged"]), (2, 1, 0))
        self.assertEqual((second["advancing"], second["declining"], second["unchanged"]), (1, 0, 2))
        self.assertEqual(second["net_advances"], 1)

    def test_unmatched_timestamps_are_not_interpolated(self):
        result = build_market_breadth_report({
            "A": history([10, 11, 12]),
            "B": history([20, 21, 22], [
                "2026-01-01T00:00:00+00:00",
                "2026-01-02T00:00:00+00:00",
                "2026-02-03T00:00:00+00:00",
            ]),
        })
        self.assertEqual([row["timestamp"] for row in result["observations"]], [
            "2026-01-02T00:00:00+00:00"
        ])

    def test_insufficient_timestamp_coverage_is_omitted(self):
        result = build_market_breadth_report({
            "A": history([10, 11]),
            "B": history([20, 21], ["2026-02-01T00:00:00+00:00", "2026-02-02T00:00:00+00:00"]),
        })
        self.assertEqual(result["observations"], [])
        self.assertIsNone(result["latest_observation"])

    def test_requires_two_symbols_and_minimum_coverage(self):
        with self.assertRaises(ValueError):
            build_market_breadth_report({"A": history([1, 2])})
        with self.assertRaises(ValueError):
            build_market_breadth_report({"A": history([1, 2]), "B": history([2, 3])}, min_symbols=1)


if __name__ == "__main__":
    unittest.main()
