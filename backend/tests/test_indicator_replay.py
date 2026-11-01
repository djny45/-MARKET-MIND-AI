import unittest

from app.indicator_replay import build_indicator_replay_report


def history(count=80):
    bars = []
    for index in range(count):
        close = 100 + index * 0.2 + (index % 7) * 0.15
        bars.append({
            "timestamp": f"2026-01-{(index % 28) + 1:02d}T{index % 24:02d}:00:00+00:00",
            "close": close,
            "source": "test-fixture",
            "status": "historical",
        })
    return {"symbol": "TEST", "interval": "1h", "bars": bars}


class IndicatorReplayTests(unittest.TestCase):
    def test_prefix_replay_matches_full_series_at_checkpoints(self):
        result = build_indicator_replay_report(history())
        self.assertEqual(result["mode"], "historical_prefix_replay")
        self.assertEqual(result["bars_replayed"], 80)
        self.assertEqual(result["causal_consistency"], "pass")
        self.assertEqual(result["mismatch_count"], 0)
        self.assertGreaterEqual(result["checkpoint_count"], 2)
        self.assertTrue(all(item["mismatch_count"] == 0 for item in result["comparisons"]))

    def test_replay_reports_source_timestamp_and_market_scope(self):
        result = build_indicator_replay_report(history(20), checkpoints=4)
        self.assertEqual(result["symbol"], "TEST")
        self.assertEqual(result["interval"], "1h")
        self.assertTrue(all(item["timestamp"] for item in result["comparisons"]))

    def test_invalid_or_non_finite_close_is_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), 0, "bad"):
            bars = history(10)["bars"]
            bars[4]["close"] = value
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    build_indicator_replay_report({"bars": bars})

    def test_replay_requires_bounded_input_and_checkpoints(self):
        with self.assertRaises(ValueError):
            build_indicator_replay_report({"bars": history(1)["bars"]})
        with self.assertRaises(ValueError):
            build_indicator_replay_report(history(), checkpoints=1)
        with self.assertRaises(ValueError):
            build_indicator_replay_report(history(5001))

    def test_replay_is_invariant_to_future_observations_at_existing_checkpoints(self):
        original = history(40)
        extended = {"bars": original["bars"] + history(10)["bars"]}
        first = build_indicator_replay_report(original, checkpoints=4)
        second = build_indicator_replay_report(extended, checkpoints=4)
        first_by_index = {item["bar_index"]: item for item in first["comparisons"]}
        second_by_index = {item["bar_index"]: item for item in second["comparisons"]}
        self.assertTrue(all(item["mismatch_count"] == 0 for item in first_by_index.values()))
        self.assertTrue(all(item["mismatch_count"] == 0 for item in second_by_index.values()))
        common_indices = set(first_by_index) & set(second_by_index)
        self.assertTrue(common_indices)
        for index in common_indices:
            self.assertEqual(first_by_index[index]["timestamp"], second_by_index[index]["timestamp"])
            self.assertEqual(first_by_index[index]["values"], second_by_index[index]["values"])


if __name__ == "__main__":
    unittest.main()
