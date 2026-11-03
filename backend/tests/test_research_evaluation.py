import unittest

from app.research_evaluation import validate_chronological_splits


class ChronologicalSplitTests(unittest.TestCase):
    def test_valid_utc_splits_with_embargo(self):
        result = validate_chronological_splits(
            "2024-01-31T23:59:59Z",
            "2024-02-02T00:00:00Z",
            "2024-02-29T23:59:59Z",
            "2024-03-02T00:00:00Z",
            embargo_seconds=86400,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["method"], "chronological")
        self.assertFalse(result["random_shuffling_allowed"])
        self.assertEqual(result["timezone_normalized"], "UTC")

    def test_timezone_offsets_are_compared_in_utc(self):
        result = validate_chronological_splits(
            "2024-01-01T12:00:00+05:30",
            "2024-01-01T07:00:01Z",
            "2024-01-02T07:00:00Z",
            "2024-01-02T07:00:01Z",
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["train_validation_gap_seconds"], 1801)

    def test_preserves_fractional_second_gaps(self):
        result = validate_chronological_splits(
            "2024-01-01T00:00:00.100Z",
            "2024-01-01T00:00:00.600Z",
            "2024-01-02T00:00:00.100Z",
            "2024-01-02T00:00:00.850Z",
        )
        self.assertEqual(result["train_validation_gap_seconds"], 0.5)
        self.assertEqual(result["validation_test_gap_seconds"], 0.75)

    def test_rejects_overlapping_or_out_of_order_splits(self):
        with self.assertRaisesRegex(ValueError, "validation_start must be after train_end"):
            validate_chronological_splits(
                "2024-01-02T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
                "2024-01-04T00:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "test_start must be after validation_end"):
            validate_chronological_splits(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
                "2024-01-03T00:00:00Z",
            )

    def test_rejects_missing_timezone_and_negative_embargo(self):
        with self.assertRaisesRegex(ValueError, "must include a timezone"):
            validate_chronological_splits(
                "2024-01-01T00:00:00",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
                "2024-01-04T00:00:00Z",
            )
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            validate_chronological_splits(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
                "2024-01-04T00:00:00Z",
                embargo_seconds=-1,
            )

    def test_rejects_malformed_timestamp_and_boolean_embargo(self):
        for malformed in ("not-a-date", "2024-01-01TZ00:00:00"):
            with self.subTest(timestamp=malformed):
                with self.assertRaisesRegex(ValueError, "valid ISO-8601"):
                    validate_chronological_splits(
                        malformed,
                        "2024-01-02T00:00:00Z",
                        "2024-01-03T00:00:00Z",
                        "2024-01-04T00:00:00Z",
                    )
        with self.assertRaisesRegex(ValueError, "non-negative integer"):
            validate_chronological_splits(
                "2024-01-01T00:00:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-03T00:00:00Z",
                "2024-01-04T00:00:00Z",
                embargo_seconds=True,
            )

    def test_exact_embargo_boundary_is_valid(self):
        result = validate_chronological_splits(
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:10Z",
            "2024-01-02T00:00:00Z",
            "2024-01-02T00:00:10Z",
            embargo_seconds=10,
        )
        self.assertTrue(result["valid"])
        self.assertEqual(result["train_validation_gap_seconds"], 10)
        self.assertEqual(result["validation_test_gap_seconds"], 10)

    def test_checks_embargo_for_each_split_boundary_independently(self):
        # The first gap is sufficient, but the validation/test gap is not.
        with self.assertRaisesRegex(ValueError, "validation/test boundary"):
            validate_chronological_splits(
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:01:00Z",
                "2024-01-02T00:00:00Z",
                "2024-01-02T00:00:59Z",
                embargo_seconds=60,
            )

    def test_rejects_insufficient_embargo(self):
        with self.assertRaisesRegex(ValueError, "does not satisfy embargo_seconds"):
            validate_chronological_splits(
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:01Z",
                "2024-01-02T00:00:00Z",
                "2024-01-02T00:00:01Z",
                embargo_seconds=60,
            )


class DatasetManifestTests(unittest.TestCase):
    def valid_manifest(self):
        return {
            "dataset_id": "demo-ohlcv-001",
            "source": "local_fixture",
            "symbol": "TEST-USD",
            "timeframe": "1h",
            "start": "2024-01-01T00:00:00Z",
            "end": "2024-02-01T00:00:00Z",
            "sample_count": 744,
            "missing_fraction": 0.0,
            "synthetic": False,
        }

    def test_valid_manifest_is_normalized_and_marked_ready(self):
        from app.research_evaluation import validate_dataset_manifest

        result = validate_dataset_manifest(self.valid_manifest())
        self.assertTrue(result["metadata_valid"])
        self.assertTrue(result["evaluation_ready"])
        self.assertEqual(result["sample_count"], 744)
        self.assertEqual(result["start"], "2024-01-01T00:00:00+00:00")
        self.assertTrue(result["research_only"])
        self.assertTrue(result["limitations"])

    def test_synthetic_or_missing_data_is_not_marked_ready(self):
        from app.research_evaluation import validate_dataset_manifest

        manifest = self.valid_manifest()
        manifest["synthetic"] = True
        self.assertFalse(validate_dataset_manifest(manifest)["evaluation_ready"])
        manifest["synthetic"] = False
        manifest["missing_fraction"] = 0.01
        self.assertFalse(validate_dataset_manifest(manifest)["evaluation_ready"])

    def test_rejects_invalid_required_fields_and_time_range(self):
        from app.research_evaluation import validate_dataset_manifest

        for field, value in (("source", " "), ("sample_count", 0), ("sample_count", True)):
            manifest = self.valid_manifest()
            manifest[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(ValueError):
                    validate_dataset_manifest(manifest)

        manifest = self.valid_manifest()
        manifest["end"] = manifest["start"]
        with self.assertRaisesRegex(ValueError, "end must be after start"):
            validate_dataset_manifest(manifest)

    def test_rejects_invalid_missing_fraction_and_timezone(self):
        from app.research_evaluation import validate_dataset_manifest

        for value in (-0.1, 1.1, True, "0.2"):
            manifest = self.valid_manifest()
            manifest["missing_fraction"] = value
            with self.subTest(missing_fraction=value):
                with self.assertRaisesRegex(ValueError, "missing_fraction"):
                    validate_dataset_manifest(manifest)

        manifest = self.valid_manifest()
        manifest["start"] = "2024-01-01T00:00:00"
        with self.assertRaisesRegex(ValueError, "must include a timezone"):
            validate_dataset_manifest(manifest)



class BinaryResearchMetricsTests(unittest.TestCase):
    def test_metrics_and_majority_baseline(self):
        from app.research_evaluation import evaluate_binary_predictions

        result = evaluate_binary_predictions([1, 1, 0, 0], [1, 0, 0, 0])
        self.assertEqual(result["sample_count"], 4)
        self.assertEqual(result["confusion_matrix"], {
            "true_positive": 1, "true_negative": 2,
            "false_positive": 0, "false_negative": 1,
        })
        self.assertEqual(result["accuracy"], 0.75)
        self.assertEqual(result["precision"], 1.0)
        self.assertEqual(result["recall"], 0.5)
        self.assertEqual(result["specificity"], 1.0)
        self.assertEqual(result["balanced_accuracy"], 0.75)
        self.assertEqual(result["positive_label_prevalence"], 0.5)
        self.assertEqual(result["predicted_positive_fraction"], 0.25)
        self.assertAlmostEqual(result["f1"], 2 / 3)
        self.assertEqual(result["majority_class_baseline_accuracy"], 0.5)
        self.assertEqual(result["accuracy_delta_vs_majority_baseline"], 0.25)
        self.assertTrue(result["research_only"])

    def test_handles_zero_division_without_crashing(self):
        from app.research_evaluation import evaluate_binary_predictions

        result = evaluate_binary_predictions([0, 0, 0], [0, 0, 0])
        self.assertEqual(result["precision"], 0.0)
        self.assertEqual(result["recall"], 0.0)
        self.assertEqual(result["f1"], 0.0)
        self.assertEqual(result["accuracy"], 1.0)

    def test_rejects_empty_mismatched_and_non_binary_inputs(self):
        from app.research_evaluation import evaluate_binary_predictions

        cases = (([], []), ([1], [1, 0]), ([0, 2], [0, 1]), ([True], [1]), ([0], ["0"]))
        for actual, predicted in cases:
            with self.subTest(actual=actual, predicted=predicted):
                with self.assertRaises(ValueError):
                    evaluate_binary_predictions(actual, predicted)

    def test_rejects_non_sequence_inputs(self):
        from app.research_evaluation import evaluate_binary_predictions

        with self.assertRaisesRegex(ValueError, "lists or tuples"):
            evaluate_binary_predictions(None, [0])


class BinaryEvaluationAggregationTests(unittest.TestCase):
    def test_returns_fold_metrics_variance_and_pooled_metrics(self):
        from app.research_evaluation import aggregate_binary_evaluation_runs

        result = aggregate_binary_evaluation_runs(
            [[1, 1, 0, 0], [1, 0]],
            [[1, 0, 0, 0], [0, 0]],
        )
        self.assertEqual(result["split_count"], 2)
        self.assertEqual(len(result["per_split"]), 2)
        self.assertAlmostEqual(result["unweighted_split_mean"]["accuracy"], 0.625)
        self.assertAlmostEqual(result["unweighted_split_population_std"]["accuracy"], 0.125)
        self.assertEqual(result["pooled"]["sample_count"], 6)
        self.assertEqual(result["pooled"]["accuracy"], 4 / 6)
        self.assertTrue(result["research_only"])
        self.assertTrue(result["limitations"])

    def test_rejects_empty_mismatched_or_invalid_split(self):
        from app.research_evaluation import aggregate_binary_evaluation_runs

        invalid_cases = (
            ([], []),
            ([[0]], [[0], [1]]),
            ([[0, 2]], [[0, 1]]),
        )
        for actual, predicted in invalid_cases:
            with self.subTest(actual=actual, predicted=predicted):
                with self.assertRaises(ValueError):
                    aggregate_binary_evaluation_runs(actual, predicted)

    def test_rejects_non_sequence_split_collections(self):
        from app.research_evaluation import aggregate_binary_evaluation_runs

        with self.assertRaisesRegex(ValueError, "lists or tuples"):
            aggregate_binary_evaluation_runs(None, [[0]])


class BinaryResearchReportTests(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "dataset_id": "test-market-series", "source": "local_fixture",
            "symbol": "TEST-USD", "timeframe": "1h",
            "start": "2024-01-01T00:00:00Z", "end": "2024-02-01T00:00:00Z",
            "sample_count": 100, "missing_fraction": 0.0, "synthetic": False,
        }
        self.boundaries = {
            "train_end": "2024-01-10T00:00:00Z",
            "validation_start": "2024-01-11T00:00:00Z",
            "validation_end": "2024-01-20T00:00:00Z",
            "test_start": "2024-01-21T00:00:00Z",
        }

    def test_builds_report_from_manifest_chronology_and_metrics(self):
        from app.research_evaluation import build_binary_research_report
        report = build_binary_research_report(
            self.manifest, self.boundaries,
            [[0, 1, 1], [0, 0]], [[0, 1, 0], [0, 1]],
        )
        self.assertEqual(report["report_type"], "binary_classification_research")
        self.assertEqual(report["dataset"]["dataset_id"], "test-market-series")
        self.assertTrue(report["chronology"]["valid"])
        self.assertEqual(report["evaluated_sample_count"], 5)
        self.assertEqual(report["metrics"]["split_count"], 2)
        self.assertTrue(report["research_only"])
        self.assertTrue(report["limitations"])

    def test_rejects_manifest_not_ready(self):
        from app.research_evaluation import build_binary_research_report
        manifest = dict(self.manifest)
        manifest["synthetic"] = True
        with self.assertRaisesRegex(ValueError, "not evaluation-ready"):
            build_binary_research_report(manifest, self.boundaries, [[0]], [[0]])

    def test_rejects_missing_boundaries_and_sample_overflow(self):
        from app.research_evaluation import build_binary_research_report
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            build_binary_research_report(
                self.manifest, {"train_end": "2024-01-10T00:00:00Z"}, [[0]], [[0]]
            )
        manifest = dict(self.manifest)
        manifest["sample_count"] = 1
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            build_binary_research_report(
                manifest, self.boundaries, [[0, 1]], [[0, 1]]
            )


class HistoricalForecastingTests(unittest.TestCase):
    def test_chronological_forecast_returns_test_metrics_and_baseline(self):
        import math
        from app.historical_forecasting import evaluate_next_day_return_forecast

        # Deterministic synthetic prices are test fixtures only, not market data.
        prices = [100.0 * math.exp(0.001 * i + 0.01 * math.sin(i / 5)) for i in range(180)]
        result = evaluate_next_day_return_forecast(prices)
        self.assertEqual(result["task"], "next_day_log_return_forecast")
        self.assertFalse(result["split"]["shuffle"])
        self.assertGreater(result["split"]["train_samples"], result["split"]["validation_samples"])
        self.assertGreater(result["test_model"]["sample_count"], 0)
        self.assertEqual(
            result["test_model"]["sample_count"],
            result["test_zero_return_baseline"]["sample_count"],
        )
        self.assertTrue(result["research_only"])
        self.assertTrue(result["limitations"])

    def test_rejects_invalid_prices_lookback_and_short_history(self):
        from app.historical_forecasting import evaluate_next_day_return_forecast

        for prices in ([100, 0, 101], [100, float("nan"), 101], [100, -1, 101]):
            with self.subTest(prices=prices):
                with self.assertRaises(ValueError):
                    evaluate_next_day_return_forecast(prices)
        with self.assertRaisesRegex(ValueError, "lookback"):
            evaluate_next_day_return_forecast([100.0] * 120, lookback=True)
        with self.assertRaisesRegex(ValueError, "insufficient history"):
            evaluate_next_day_return_forecast([100.0, 101.0, 102.0])


if __name__ == "__main__":
    unittest.main()
