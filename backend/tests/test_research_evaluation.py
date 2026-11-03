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


if __name__ == "__main__":
    unittest.main()
