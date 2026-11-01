import unittest

from app.source_indicator_comparison import compare_source_indicator_series


def bars(source, multiplier=1.0):
    result = []
    for index in range(40):
        close = (100 + index * 0.4 + (index % 5) * 0.2) * multiplier
        result.append({
            "timestamp": f"2026-01-{(index // 24) + 1:02d}T{index % 24:02d}:00:00+00:00",
            "source": source, "close": close,
        })
    return result


class SourceIndicatorComparisonTests(unittest.TestCase):
    def test_independent_sources_compare_at_shared_instants(self):
        result = compare_source_indicator_series({
            "symbol": "TEST", "interval": "1h",
            "bars": bars("alpha") + bars("beta", 1.1),
        })
        self.assertEqual(result["evaluated_source_count"], 2)
        self.assertEqual(result["shared_timestamp_count"], 40)
        self.assertEqual(result["comparison_count"], 40 * 8)
        self.assertEqual(result["source_reports"]["alpha"]["status"], "evaluated")
        self.assertNotEqual(
            result["comparisons"][10]["field_ranges"]["ema_20"]["absolute_spread"], 0
        )

    def test_identical_source_data_has_zero_indicator_spread(self):
        result = compare_source_indicator_series({
            "bars": bars("alpha") + bars("beta")
        })
        for comparison in result["comparisons"]:
            for field in comparison["field_ranges"].values():
                if field["valid_source_count"] == 2:
                    self.assertEqual(field["absolute_spread"], 0)

    def test_timezone_equivalent_timestamps_align(self):
        first = bars("alpha")[:3]
        second = bars("beta")[:3]
        second[0]["timestamp"] = "2026-01-01T01:00:00+01:00"
        result = compare_source_indicator_series({"bars": first + second})
        self.assertEqual(result["shared_timestamp_count"], 3)

    def test_duplicate_source_instants_block_that_source(self):
        first = bars("alpha")
        second = bars("beta")
        second.append({**second[0], "timestamp": "2026-01-01T01:00:00+01:00"})
        result = compare_source_indicator_series({"bars": first + second})
        self.assertEqual(result["source_reports"]["beta"]["status"], "blocked_duplicate_instants")
        self.assertEqual(result["evaluated_source_count"], 1)
        self.assertEqual(result["shared_timestamp_count"], 0)

    def test_invalid_close_blocks_source_instead_of_silently_skipping(self):
        first = bars("alpha")
        first[4]["close"] = float("nan")
        result = compare_source_indicator_series({"bars": first + bars("beta")})
        self.assertEqual(result["source_reports"]["alpha"]["status"], "blocked_invalid_observations")
        self.assertEqual(result["source_reports"]["alpha"]["invalid_observation_count"], 1)

    def test_revision_policy_annotates_excludes_and_blocks_revised_source_rows(self):
        first = bars("alpha")
        second = bars("beta")
        revised = [{"source": "alpha", "timestamp": first[5]["timestamp"]}]
        annotated = compare_source_indicator_series(
            {"bars": first + second}, revisioned_keys=revised
        )
        self.assertEqual(annotated["source_reports"]["alpha"]["revised_observation_count"], 1)
        self.assertTrue(annotated["source_reports"]["alpha"]["revision_review_required"])
        excluded = compare_source_indicator_series(
            {"bars": first + second}, revisioned_keys=revised,
            revision_policy="exclude_revised",
        )
        self.assertEqual(excluded["source_reports"]["alpha"]["valid_observation_count"], 39)
        self.assertEqual(excluded["source_reports"]["alpha"]["excluded_revised_observation_count"], 1)
        blocked = compare_source_indicator_series(
            {"bars": first + second}, revisioned_keys=revised,
            revision_policy="block_revised",
        )
        self.assertEqual(blocked["source_reports"]["alpha"]["status"], "blocked_revised_observations")
        self.assertEqual(blocked["evaluated_source_count"], 1)

    def test_unknown_revision_policy_is_rejected(self):
        with self.assertRaises(ValueError):
            compare_source_indicator_series({"bars": bars("alpha")}, revision_policy="ignore")

    def test_single_source_returns_no_cross_source_comparisons(self):
        result = compare_source_indicator_series({"bars": bars("alpha")})
        self.assertEqual(result["source_count"], 1)
        self.assertEqual(result["comparisons"], [])


if __name__ == "__main__":
    unittest.main()
