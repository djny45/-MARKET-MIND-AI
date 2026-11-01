import unittest

from app.evaluation_manifest import build_evaluation_manifest


def bars(source="feed-a", count=100):
    result = []
    for index in range(count):
        result.append({
            "timestamp": f"2026-01-{(index // 24) + 1:02d}T{index % 24:02d}:00:00+00:00",
            "open": 100 + index, "high": 102 + index,
            "low": 99 + index, "close": 101 + index,
            "volume": 1000 + index, "source": source,
            "status": "historical", "retrieved_at": "2026-11-01T00:00:00+00:00",
        })
    return result


class EvaluationManifestTests(unittest.TestCase):
    def test_creates_chronological_non_overlapping_partitions_with_embargo(self):
        result = build_evaluation_manifest({
            "symbol": "TEST", "interval": "1h", "bars": bars()
        })
        report = result["source_manifests"]["feed-a"]
        self.assertEqual(report["status"], "ready")
        parts = report["partitions"]
        self.assertEqual(parts["development"]["observation_count"], 60)
        self.assertEqual(parts["validation"]["observation_count"], 19)
        self.assertEqual(parts["holdout"]["observation_count"], 19)
        self.assertEqual(len(report["embargo"]), 2)
        self.assertLess(
            parts["development"]["last_timestamp_utc"],
            parts["validation"]["first_timestamp_utc"],
        )
        self.assertLess(
            parts["validation"]["last_timestamp_utc"],
            parts["holdout"]["first_timestamp_utc"],
        )

    def test_each_source_is_partitioned_independently(self):
        result = build_evaluation_manifest({
            "bars": bars("alpha", 100) + bars("beta", 80)
        })
        self.assertEqual(result["ready_source_count"], 2)
        self.assertEqual(
            result["source_manifests"]["alpha"]["partitions"]["development"]["observation_count"],
            60,
        )
        self.assertEqual(
            result["source_manifests"]["beta"]["partitions"]["development"]["observation_count"],
            48,
        )
        self.assertNotEqual(
            result["source_manifests"]["alpha"]["dataset_sha256"],
            result["source_manifests"]["beta"]["dataset_sha256"],
        )

    def test_digest_is_stable_and_changes_when_data_changes(self):
        original = {"bars": bars(count=50)}
        first = build_evaluation_manifest(original)
        second = build_evaluation_manifest(original)
        self.assertEqual(
            first["source_manifests"]["feed-a"]["dataset_sha256"],
            second["source_manifests"]["feed-a"]["dataset_sha256"],
        )
        changed = {"bars": bars(count=50)}
        changed["bars"][10]["close"] += 0.01
        third = build_evaluation_manifest(changed)
        self.assertNotEqual(
            first["source_manifests"]["feed-a"]["dataset_sha256"],
            third["source_manifests"]["feed-a"]["dataset_sha256"],
        )

    def test_invalid_timestamp_and_non_finite_values_block_source(self):
        bad_timestamp = bars(count=20)
        bad_timestamp[3]["timestamp"] = "not-a-time"
        result = build_evaluation_manifest({"bars": bad_timestamp})
        self.assertEqual(
            result["source_manifests"]["feed-a"]["status"],
            "blocked_invalid_observations",
        )
        bad_close = bars("feed-b", 20)
        bad_close[3]["close"] = float("nan")
        result = build_evaluation_manifest({"bars": bad_close})
        self.assertEqual(
            result["source_manifests"]["feed-b"]["status"],
            "blocked_invalid_observations",
        )

    def test_duplicate_source_instants_block_source(self):
        data = bars(count=20)
        data[1]["timestamp"] = data[0]["timestamp"]
        result = build_evaluation_manifest({"bars": data})
        self.assertEqual(
            result["source_manifests"]["feed-a"]["status"],
            "blocked_duplicate_timestamps",
        )

    def test_small_source_and_too_large_embargo_are_reported(self):
        result = build_evaluation_manifest({"bars": bars(count=8)})
        self.assertEqual(result["source_manifests"]["feed-a"]["status"], "insufficient_history")
        result = build_evaluation_manifest({"bars": bars(count=10)}, embargo_bars=10)
        self.assertEqual(
            result["source_manifests"]["feed-a"]["status"],
            "insufficient_history_for_embargo",
        )

    def test_rejects_invalid_split_parameters(self):
        for kwargs in (
            {"train_ratio": float("nan")},
            {"train_ratio": 0.9},
            {"validation_ratio": 0.01},
            {"train_ratio": 0.8, "validation_ratio": 0.2},
            {"embargo_bars": -1},
            {"embargo_bars": True},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    build_evaluation_manifest({"bars": bars()}, **kwargs)


    def test_revision_policy_annotates_revised_observations_by_default(self):
        data = bars(count=30)
        revised = [{"source": "feed-a", "timestamp": data[5]["timestamp"]}]
        result = build_evaluation_manifest({"bars": data}, revisioned_keys=revised)
        report = result["source_manifests"]["feed-a"]
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["revised_observation_count"], 1)
        self.assertTrue(report["revision_review_required"])
        self.assertEqual(report["excluded_revised_observation_count"], 0)

    def test_revision_policy_excludes_revised_rows_before_partitioning(self):
        data = bars(count=30)
        revised = [{"source": "feed-a", "timestamp": data[5]["timestamp"]}]
        result = build_evaluation_manifest(
            {"bars": data}, revisioned_keys=revised, revision_policy="exclude_revised"
        )
        report = result["source_manifests"]["feed-a"]
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["observation_count"], 29)
        self.assertEqual(report["excluded_revised_observation_count"], 1)
        self.assertFalse(report["revision_review_required"])

    def test_revision_policy_blocks_source_with_revised_observation(self):
        data = bars(count=30)
        revised = [{"source": "feed-a", "timestamp": data[5]["timestamp"]}]
        result = build_evaluation_manifest(
            {"bars": data}, revisioned_keys=revised, revision_policy="block_revised"
        )
        report = result["source_manifests"]["feed-a"]
        self.assertEqual(report["status"], "blocked_revised_observations")
        self.assertEqual(report["revised_observation_count"], 1)
        self.assertEqual(report["partitions"], {})

    def test_revision_policy_rejects_unknown_value(self):
        with self.assertRaises(ValueError):
            build_evaluation_manifest({"bars": bars()}, revision_policy="ignore")

    def test_empty_history_is_a_valid_empty_manifest(self):
        result = build_evaluation_manifest({"symbol": "TEST", "bars": []})
        self.assertEqual(result["source_count"], 0)
        self.assertEqual(result["ready_source_count"], 0)
        self.assertEqual(result["partitioned_observation_count"], 0)


if __name__ == "__main__":
    unittest.main()
