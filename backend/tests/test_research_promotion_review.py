import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.research_benchmark import run_offline_research_benchmark
from app.research_benchmark_record import serialize_benchmark_record
from app.research_benchmark_store import BenchmarkRecordStore
from app.research_promotion_review import PromotionReviewStore, promotion_eligibility


def result(with_baseline=True):
    cases = [{
        "case_id": "promotion-fixture",
        "draft": "Synthetic fixture draft.",
        "claims": [{"text": "Fixture", "source_refs": ["s1"]}],
        "source_registry": [{"source_id": "s1"}],
    }]
    initial = run_offline_research_benchmark(cases)
    if not with_baseline:
        return initial
    baseline_metrics = {key: value["mean"] for key, value in initial["aggregate_metrics"].items()}
    return run_offline_research_benchmark(cases, baseline={"metrics": baseline_metrics})


class PromotionReviewStoreTests(unittest.TestCase):
    def test_approval_requires_complete_clean_benchmark_and_is_retrievable(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(result())
            reviews = PromotionReviewStore(db)
            reviews.submit_review(
                proposal_id="proposal-1", benchmark_record_id=record_id,
                candidate_config={"temperature": 0.2, "enabled": False},
                decision="approved", reviewer="reviewer-1",
                rationale="Reviewed fixture evidence.",
            )
            review = reviews.get_review("proposal-1")
            self.assertEqual(review["decision"], "approved")
            self.assertEqual(review["candidate_config"]["temperature"], 0.2)
            self.assertEqual(len(reviews.list_reviews()), 1)

    def test_approval_blocked_without_baseline(self):
        record = json.loads(serialize_benchmark_record(result(with_baseline=False)))
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertEqual(gate["status"], "baseline_required")
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(result(with_baseline=False))
            reviews = PromotionReviewStore(db)
            with self.assertRaisesRegex(ValueError, "baseline comparison is missing"):
                reviews.submit_review(
                    proposal_id="proposal-no-baseline", benchmark_record_id=record_id,
                    candidate_config={}, decision="approved", reviewer="reviewer",
                    rationale="Baseline absent.",
                )

    def test_incomplete_comparison_blocks_approval_but_rejection_is_recordable(self):
        incomplete = run_offline_research_benchmark(
            [{"case_id": "incomplete", "draft": "Fixture with missing metric values.",
              "claims": [], "source_registry": []}],
            baseline={"metrics": {"claim_reference_coverage": 0.8,
                                  "known_source_reference_coverage": 0.8}},
        )
        record = json.loads(serialize_benchmark_record(incomplete))
        self.assertFalse(promotion_eligibility(record)["eligible"])
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(incomplete)
            reviews = PromotionReviewStore(db)
            kwargs = dict(proposal_id="proposal-incomplete", benchmark_record_id=record_id,
                          candidate_config={}, reviewer="reviewer",
                          rationale="Comparison incomplete; reject for now.")
            with self.assertRaisesRegex(ValueError, "skipped comparisons"):
                reviews.submit_review(decision="approved", **kwargs)
            reviews.submit_review(decision="rejected", **kwargs)
            self.assertEqual(reviews.get_review("proposal-incomplete")["decision"], "rejected")

    def test_gate_rejects_forged_delta_and_missing_metric(self):
        record = json.loads(serialize_benchmark_record(result()))
        comparison = record["result"]["baseline_comparison"]
        metric = next(iter(comparison))
        comparison[metric]["delta"] = 0.1234
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertTrue(any("delta is inconsistent" in reason for reason in gate["reasons"]))

        record = json.loads(serialize_benchmark_record(result()))
        record["result"]["baseline_comparison"].pop(metric)
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertTrue(any("metric set is incomplete" in reason for reason in gate["reasons"]))

    def test_gate_recomputes_regression_summary_from_comparisons(self):
        benchmark = result()
        benchmark["regression_summary"]["items"] = [{
            "metric": "claim_reference_coverage",
            "delta": -0.9,
            "threshold": 0.05,
            "severity": "regression",
        }]
        record = json.loads(serialize_benchmark_record(benchmark))
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertIn(
            "benchmark regression items are inconsistent with metric deltas",
            gate["reasons"],
        )

        benchmark = result()
        benchmark["regression_summary"]["skipped_comparison_count"] = 1
        record = json.loads(serialize_benchmark_record(benchmark))
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertIn(
            "benchmark skipped-comparison count is inconsistent",
            gate["reasons"],
        )

    def test_gate_rejects_tampered_record_result_and_envelope(self):
        record = json.loads(serialize_benchmark_record(result()))
        record["result"]["aggregate_metrics"]["tampered_metric"] = {"mean": 1.0}
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertIn("benchmark record content hash is invalid", gate["reasons"])

        record = json.loads(serialize_benchmark_record(result()))
        record["benchmark_id"] = "different-benchmark"
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertIn("benchmark ID does not match record result", gate["reasons"])

        record = json.loads(serialize_benchmark_record(result()))
        record["record_schema_version"] = 999
        gate = promotion_eligibility(record)
        self.assertFalse(gate["eligible"])
        self.assertIn("benchmark record schema version is unsupported", gate["reasons"])

    def test_missing_benchmark_record_is_rejected_by_foreign_key(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            reviews = PromotionReviewStore(db)
            with self.assertRaises(sqlite3.IntegrityError):
                reviews.submit_review(
                    proposal_id="proposal-unknown", benchmark_record_id="missing-record",
                    candidate_config={}, decision="rejected", reviewer="reviewer",
                    rationale="No linked benchmark record.",
                )

    def test_review_decision_and_duplicate_proposal_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(result())
            reviews = PromotionReviewStore(db)
            kwargs = dict(proposal_id="proposal-2", benchmark_record_id=record_id,
                          candidate_config={"mode": "candidate"}, reviewer="reviewer",
                          rationale="Test decision validation.")
            with self.assertRaises(ValueError):
                reviews.submit_review(decision="pending", **kwargs)
            reviews.submit_review(decision="rejected", **kwargs)
            with self.assertRaises(sqlite3.IntegrityError):
                reviews.submit_review(decision="approved", **kwargs)

    def test_rejects_non_json_candidate_config(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(result())
            reviews = PromotionReviewStore(db)
            with self.assertRaises(ValueError):
                reviews.submit_review(
                    proposal_id="proposal-bad", benchmark_record_id=record_id,
                    candidate_config={"bad": object()}, decision="rejected",
                    reviewer="reviewer", rationale="Invalid config serialization.",
                )


if __name__ == "__main__":
    unittest.main()
