import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app.research_benchmark import run_offline_research_benchmark
from app.research_benchmark_store import BenchmarkRecordStore
from app.research_promotion_review import PromotionReviewStore


def result():
    return run_offline_research_benchmark([{
        "case_id": "promotion-fixture",
        "draft": "Synthetic fixture draft.",
        "claims": [{"text": "Fixture", "source_refs": ["s1"]}],
        "source_registry": [{"source_id": "s1"}],
    }])


class PromotionReviewStoreTests(unittest.TestCase):
    def test_review_requires_existing_benchmark_and_is_retrievable(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(result())
            reviews = PromotionReviewStore(db)
            reviews.submit_review(
                proposal_id="proposal-1",
                benchmark_record_id=record_id,
                candidate_config={"temperature": 0.2, "enabled": False},
                decision="approved",
                reviewer="reviewer-1",
                rationale="Reviewed fixture evidence.",
            )
            review = reviews.get_review("proposal-1")
            self.assertEqual(review["decision"], "approved")
            self.assertEqual(review["candidate_config"]["temperature"], 0.2)
            self.assertEqual(len(reviews.list_reviews()), 1)

    def test_missing_benchmark_record_is_rejected_by_foreign_key(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            reviews = PromotionReviewStore(db)
            with self.assertRaises(sqlite3.IntegrityError):
                reviews.submit_review(
                    proposal_id="proposal-unknown",
                    benchmark_record_id="missing-record",
                    candidate_config={},
                    decision="approved",
                    reviewer="reviewer",
                    rationale="No linked benchmark record.",
                )

    def test_review_decision_and_duplicate_proposal_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "review.sqlite"
            record_id = BenchmarkRecordStore(db).save(result())
            reviews = PromotionReviewStore(db)
            kwargs = dict(
                proposal_id="proposal-2",
                benchmark_record_id=record_id,
                candidate_config={"mode": "candidate"},
                reviewer="reviewer",
                rationale="Test decision validation.",
            )
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
                    proposal_id="proposal-bad",
                    benchmark_record_id=record_id,
                    candidate_config={"bad": object()},
                    decision="rejected",
                    reviewer="reviewer",
                    rationale="Invalid config serialization.",
                )


if __name__ == "__main__":
    unittest.main()
