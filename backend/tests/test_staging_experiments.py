import os
import tempfile
import unittest
from unittest.mock import patch

from app.worker_memory import append_memory, review_improvement_proposal
from app.staging_experiments import create_staging_experiment, run_staging_benchmark, list_staging_experiments


class StagingExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"MARKET_MIND_DB": os.path.join(self.temp.name, "staging.sqlite")})
        self.env.start()
        self.proposal = append_memory("worker_001", "method_note", {
            "update_proposal": {"title": "Improve source timestamp handling"}
        })

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def _payload(self):
        return {"benchmark_id": "fixture-bench-01", "reviewer": "human-reviewer",
                "baseline_metrics": {"coverage": 0.7, "traceability": 0.8},
                "candidate_metrics": {"coverage": 0.75, "traceability": 0.8},
                "notes": "Metrics supplied from isolated fixture run"}

    def test_staging_experiment_requires_latest_approval(self):
        with self.assertRaisesRegex(ValueError, "approved_for_staging"):
            create_staging_experiment("worker_001", self.proposal["memory_id"], self._payload())
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        saved = create_staging_experiment("worker_001", self.proposal["memory_id"], self._payload())
        self.assertEqual(saved["content"]["record_type"], "staging_experiment_result")
        self.assertEqual(saved["content"]["outcome"], "inconclusive")
        self.assertEqual(saved["content"]["execution_mode"], "reviewer_supplied_metrics_only")
        self.assertEqual(list_staging_experiments("worker_001")["count"], 1)

    def test_latest_review_revokes_staging_permission(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer-a")
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "needs_revision", "reviewer-b")
        with self.assertRaisesRegex(ValueError, "latest review status"):
            create_staging_experiment("worker_001", self.proposal["memory_id"], self._payload())

    def test_rejects_wrong_worker_and_malformed_metrics(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        with self.assertRaises(ValueError):
            create_staging_experiment("worker_002", self.proposal["memory_id"], self._payload())
        bad = self._payload()
        bad["candidate_metrics"] = {"coverage": float("nan")}
        with self.assertRaisesRegex(ValueError, "finite"):
            create_staging_experiment("worker_001", self.proposal["memory_id"], bad)


    def _benchmark_cases(self, source_id="known"):
        return [{
            "case_id": "fixture-one",
            "draft": "Synthetic evidence note.",
            "claims": [{"text": "Fixture claim", "source_refs": [source_id]}],
            "source_registry": [{"source_id": "known"}],
        }]

    def test_runs_fixture_benchmark_and_persists_reproducibility_ids(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        result = run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": self._benchmark_cases("missing"),
            "candidate_cases": self._benchmark_cases("known"),
            "reviewer": "reviewer", "notes": "offline fixture test",
        })
        content = result["content"]
        self.assertEqual(content["record_type"], "staging_experiment_result")
        self.assertEqual(content["outcome"], "inconclusive")
        self.assertIn("baseline_benchmark_id", content["benchmark_runs"])
        saved = list_staging_experiments("worker_001")["experiments"][0]
        self.assertIn("candidate_benchmark_id", saved["content"]["benchmark_runs"])

    def test_paired_case_comparison_records_metric_deltas_and_regressions(self):
        review_improvement_proposal('worker_001', self.proposal['memory_id'],
                                    'approved_for_staging', 'reviewer')
        result = run_staging_benchmark('worker_001', self.proposal['memory_id'], {
            'baseline_cases': self._benchmark_cases('known'),
            'candidate_cases': self._benchmark_cases('missing'),
            'reviewer': 'reviewer',
        })
        paired = result['content']['benchmark_runs']
        self.assertEqual(paired['paired_case_summary']['paired_case_count'], 1)
        self.assertEqual(paired['paired_case_summary']['regression_count'], 1)
        delta = paired['paired_case_metrics']['fixture-one']['known_source_reference_coverage']['delta']
        self.assertEqual(delta, -1.0)

    def test_paired_benchmark_rejects_different_case_ids(self):
        review_improvement_proposal('worker_001', self.proposal['memory_id'],
                                    'approved_for_staging', 'reviewer')
        baseline = self._benchmark_cases()
        candidate = self._benchmark_cases()
        candidate[0]['case_id'] = 'different-case'
        with self.assertRaisesRegex(ValueError, 'same case_id'):
            run_staging_benchmark('worker_001', self.proposal['memory_id'], {
                'baseline_cases': baseline, 'candidate_cases': candidate,
                'reviewer': 'reviewer',
            })

    def test_fixture_benchmark_still_requires_approved_proposal(self):
        with self.assertRaisesRegex(ValueError, "approved_for_staging"):
            run_staging_benchmark("worker_001", self.proposal["memory_id"], {
                "baseline_cases": self._benchmark_cases(),
                "candidate_cases": self._benchmark_cases(),
                "reviewer": "reviewer",
            })

    def test_identical_metrics_are_no_material_change(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        payload = self._payload()
        payload["candidate_metrics"] = dict(payload["baseline_metrics"])
        result = create_staging_experiment("worker_001", self.proposal["memory_id"], payload)
        self.assertEqual(result["content"]["outcome"], "no_material_change")


    def test_config_patch_evaluation_applies_only_whitelisted_candidate_config(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        cases = self._benchmark_cases()
        result = run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": cases,
            "candidate_cases": cases,
            "config_patch": {"uncertainty_markers": ["synthetic"]},
            "reviewer": "reviewer",
            "notes": "bounded config experiment",
        })
        saved = result["content"]["benchmark_runs"]
        self.assertEqual(saved["config_patch"], {"uncertainty_markers": ["synthetic"]})
        self.assertEqual(saved["config_patch_mode"], "whitelisted_evaluator_config_only")
        self.assertEqual(saved["paired_case_summary"]["paired_case_count"], 1)

    def test_config_patch_rejects_unknown_setting(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        with self.assertRaisesRegex(ValueError, "supports only"):
            run_staging_benchmark("worker_001", self.proposal["memory_id"], {
                "baseline_cases": self._benchmark_cases(),
                "candidate_cases": self._benchmark_cases(),
                "config_patch": {"allow_arbitrary_code": True},
                "reviewer": "reviewer",
            })


if __name__ == "__main__":
    unittest.main()
