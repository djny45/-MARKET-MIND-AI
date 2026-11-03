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

    def test_rejects_insufficient_embargo(self):
        with self.assertRaisesRegex(ValueError, "does not satisfy embargo_seconds"):
            validate_chronological_splits(
                "2024-01-01T00:00:00Z",
                "2024-01-01T00:00:01Z",
                "2024-01-02T00:00:00Z",
                "2024-01-02T00:00:01Z",
                embargo_seconds=60,
            )


if __name__ == "__main__":
    unittest.main()
