import os
import tempfile
import unittest
from unittest.mock import patch

from app.worker_memory import append_memory, review_improvement_proposal
from app.staging_experiments import create_staging_experiment, run_staging_benchmark, list_staging_experiments, summarize_staging_experiments, summarize_repeatability, summarize_research_quality_dashboard, summarize_staging_provenance, verify_benchmark_record_evidence


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

    def test_staging_record_contains_stable_paired_case_id_digest(self):
        import hashlib
        import json

        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        baseline = [
            {"case_id": "fixture-z", "draft": "Evidence z",
             "claims": [{"text": "Claim z", "source_refs": ["known"]}],
             "source_registry": [{"source_id": "known"}]},
            {"case_id": "fixture-a", "draft": "Evidence a",
             "claims": [{"text": "Claim a", "source_refs": ["known"]}],
             "source_registry": [{"source_id": "known"}]},
        ]
        candidate = [dict(case) for case in baseline]
        result = run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": baseline,
            "candidate_cases": candidate,
            "reviewer": "reviewer",
        })
        expected = hashlib.sha256(
            json.dumps(["fixture-a", "fixture-z"], separators=(",", ":"),
                       ensure_ascii=True).encode("utf-8")
        ).hexdigest()
        runs = result["content"]["benchmark_runs"]
        self.assertEqual(runs["paired_case_id_sha256"], expected)
        self.assertIn("case IDs only", runs["paired_case_id_fingerprint_note"])

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

    def test_duplicate_fixture_ids_are_rejected_before_evaluator_runs(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        baseline = self._benchmark_cases()
        baseline.append(dict(baseline[0]))
        candidate = self._benchmark_cases()
        with patch("app.staging_experiments.run_offline_research_benchmark") as evaluator:
            with self.assertRaisesRegex(ValueError, "case_id values must be unique"):
                run_staging_benchmark("worker_001", self.proposal["memory_id"], {
                    "baseline_cases": baseline,
                    "candidate_cases": candidate,
                    "reviewer": "reviewer",
                })
            evaluator.assert_not_called()

    def test_unpaired_fixture_ids_are_rejected_before_evaluator_runs(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        baseline = self._benchmark_cases()
        candidate = self._benchmark_cases()
        candidate[0]["case_id"] = "not-paired"
        with patch("app.staging_experiments.run_offline_research_benchmark") as evaluator:
            with self.assertRaisesRegex(ValueError, "same case_id"):
                run_staging_benchmark("worker_001", self.proposal["memory_id"], {
                    "baseline_cases": baseline,
                    "candidate_cases": candidate,
                    "reviewer": "reviewer",
                })
            evaluator.assert_not_called()

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


    def test_quality_gate_marks_gain_for_human_review_not_auto_approval(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        baseline = self._benchmark_cases("missing")
        candidate = self._benchmark_cases("known")
        result = run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": baseline,
            "candidate_cases": candidate,
            "reviewer": "reviewer",
            "min_improvement": 0.01,
        })
        gate = result["content"]["benchmark_runs"]["quality_gate"]
        self.assertEqual(gate["status"], "eligible_for_human_staging_review")
        self.assertFalse(gate["automatic_approval"])
        evidence = result["content"]["benchmark_runs"]["benchmark_record_evidence"]
        self.assertEqual(len(evidence["baseline_record_id"]), 64)
        self.assertEqual(len(evidence["candidate_record_id"]), 64)
        self.assertEqual(len(evidence["baseline_record_sha256"]), 64)
        self.assertEqual(len(evidence["candidate_record_sha256"]), 64)
        self.assertEqual(evidence["hash_algorithm"], "sha256")
        self.assertFalse(evidence["archived_payloads"])
        self.assertEqual(verify_benchmark_record_evidence(evidence)["status"], "commitments_well_formed")
        malformed = dict(evidence)
        malformed["baseline_record_sha256"] = "not-a-digest"
        self.assertEqual(verify_benchmark_record_evidence(malformed)["status"], "invalid_digest")
        self.assertFalse(verify_benchmark_record_evidence(evidence)["payload_bytes_recheckable"])

    def test_history_summary_counts_gate_status_and_metric_deltas(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": self._benchmark_cases("missing"),
            "candidate_cases": self._benchmark_cases("known"),
            "reviewer": "reviewer",
        })
        summary = summarize_staging_experiments("worker_001")
        self.assertEqual(summary["experiment_count"], 1)
        self.assertEqual(summary["quality_gate_status_counts"]["eligible_for_human_staging_review"], 1)
        self.assertIn("known_source_reference_coverage", summary["metric_delta_summary"])
        self.assertIn("statistical significance", summary["interpretation"])

    def test_repeatability_summary_groups_exact_repeated_runs(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        payload = {
            "baseline_cases": self._benchmark_cases("missing"),
            "candidate_cases": self._benchmark_cases("known"),
            "reviewer": "reviewer",
        }
        for _ in range(3):
            run_staging_benchmark("worker_001", self.proposal["memory_id"], payload)
        report = summarize_repeatability("worker_001", min_trials=3)
        self.assertEqual(report["groups_meeting_min_trials"], 1)
        group = report["repeatability_groups"][0]
        self.assertEqual(group["trial_count"], 3)
        self.assertEqual(group["consistency_label"], "uniform_gate_status")
        self.assertIn("statistical significance", report["interpretation"])

    def test_repeatability_rejects_invalid_trial_threshold(self):
        with self.assertRaisesRegex(ValueError, "min_trials"):
            summarize_repeatability("worker_001", min_trials=1)


    def test_history_summary_rejects_bad_limit(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            summarize_staging_experiments("worker_001", 0)


    def test_quality_gate_blocks_case_regression_even_when_aggregate_improves(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        # Fixture A regresses from a cited source to no citation; fixture B improves.
        baseline = [
            {"case_id": "case-a", "draft": "Evidence A", "claims": [{"text": "A", "source_refs": ["known"]}], "source_registry": [{"source_id": "known"}]},
            {"case_id": "case-b", "draft": "Evidence B", "claims": [{"text": "B", "source_refs": ["missing"]}], "source_registry": [{"source_id": "known"}]},
        ]
        candidate = [
            {"case_id": "case-a", "draft": "Evidence A", "claims": [{"text": "A", "source_refs": ["missing"]}], "source_registry": [{"source_id": "known"}]},
            {"case_id": "case-b", "draft": "Evidence B", "claims": [{"text": "B", "source_refs": ["known"]}], "source_registry": [{"source_id": "known"}]},
        ]
        result = run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": baseline, "candidate_cases": candidate, "reviewer": "reviewer",
        })
        runs = result["content"]["benchmark_runs"]
        self.assertEqual(runs["quality_gate"]["status"], "blocked_regression")
        self.assertGreaterEqual(runs["quality_gate"]["aggregate_deltas"]["claim_reference_coverage"], 0)
        self.assertGreater(runs["paired_case_summary"]["regression_count"], 0)


    def test_quality_gate_blocks_regression_and_validates_threshold(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"],
                                    "approved_for_staging", "reviewer")
        result = run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": self._benchmark_cases("known"),
            "candidate_cases": self._benchmark_cases("missing"),
            "reviewer": "reviewer",
        })
        gate = result["content"]["benchmark_runs"]["quality_gate"]
        self.assertEqual(gate["status"], "blocked_regression")
        with self.assertRaisesRegex(ValueError, "min_improvement"):
            run_staging_benchmark("worker_001", self.proposal["memory_id"], {
                "baseline_cases": self._benchmark_cases(),
                "candidate_cases": self._benchmark_cases(),
                "reviewer": "reviewer",
                "min_improvement": 0,
            })

    def test_provenance_audit_reports_missing_and_declared_metadata(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"], "approved_for_staging", "reviewer")
        run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": self._benchmark_cases(), "candidate_cases": self._benchmark_cases(),
            "reviewer": "reviewer",
            "baseline_fixture_metadata": {"dataset_name": "baseline-set", "dataset_version": "1"},
            "candidate_fixture_metadata": {"dataset_name": "candidate-set", "dataset_version": "2"},
        })
        report = summarize_staging_provenance("worker_001")
        self.assertEqual(report["record_count"], 1)
        record = report["records"][0]
        self.assertEqual(record["baseline"]["fixture_metadata"]["dataset_name"], "baseline-set")
        self.assertEqual(record["candidate"]["fixture_metadata"]["dataset_version"], "2")
        self.assertEqual(report["missing_provenance_counts"]["baseline_dataset_name_missing"], 0)

    def test_provenance_audit_handles_legacy_records(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"], "approved_for_staging", "reviewer")
        run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": self._benchmark_cases(), "candidate_cases": self._benchmark_cases(),
            "reviewer": "reviewer",
        })
        report = summarize_staging_provenance("worker_001")
        self.assertEqual(report["missing_provenance_counts"]["baseline_fixture_metadata_missing"], 1)
        self.assertEqual(report["missing_provenance_counts"]["candidate_dataset_version_missing"], 1)

    def test_provenance_audit_validates_limit(self):
        with self.assertRaises(ValueError):
            summarize_staging_provenance("worker_001", 0)

    def test_research_quality_dashboard_consolidates_gate_provenance_and_repeatability(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"], "approved_for_staging", "reviewer")
        payload = {
            "baseline_cases": self._benchmark_cases("missing"),
            "candidate_cases": self._benchmark_cases("known"),
            "reviewer": "reviewer",
            "baseline_fixture_metadata": {"dataset_name": "base", "dataset_version": "v1"},
            "candidate_fixture_metadata": {"dataset_name": "candidate", "dataset_version": "v1"},
        }
        for _ in range(3):
            run_staging_benchmark("worker_001", self.proposal["memory_id"], payload)
        dashboard = summarize_research_quality_dashboard("worker_001", limit=10)
        self.assertEqual(dashboard["experiment_count"], 3)
        self.assertEqual(dashboard["experiments_missing_dataset_name_or_version"], 0)
        self.assertEqual(dashboard["quality_gate_status_counts"]["eligible_for_human_staging_review"], 3)
        self.assertEqual(dashboard["repeatability"]["groups_meeting_min_trials"], 1)
        self.assertIn("does not validate truth", dashboard["interpretation"])

    def test_dashboard_summarizes_aggregate_delta_distribution(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"], "approved_for_staging", "reviewer")
        payload = {
            "baseline_cases": self._benchmark_cases("missing"),
            "candidate_cases": self._benchmark_cases("known"),
            "reviewer": "reviewer",
            "baseline_fixture_metadata": {"dataset_name": "base", "dataset_version": "v1"},
            "candidate_fixture_metadata": {"dataset_name": "candidate", "dataset_version": "v1"},
        }
        run_staging_benchmark("worker_001", self.proposal["memory_id"], payload)
        dashboard = summarize_research_quality_dashboard("worker_001")
        coverage = dashboard["aggregate_delta_summary"]["claim_reference_coverage"]
        self.assertEqual(coverage["observations"], 1)
        self.assertEqual(coverage["positive_count"] + coverage["negative_count"] + coverage["zero_count"], 1)
        self.assertIn("mean_delta", coverage)

    def test_dashboard_includes_fixture_overlap_flags(self):
        review_improvement_proposal("worker_001", self.proposal["memory_id"], "approved_for_staging", "reviewer")
        cases = self._benchmark_cases("missing")
        cases.append({
            "case_id": "fixture-two",
            "draft": "Independent synthetic fixture.",
            "claims": [{"text": "Separate claim", "source_refs": ["missing"]}],
            "source_registry": [{"source_id": "known"}],
        })
        cases[1]["draft"] = cases[0]["draft"]
        cases[1]["claims"] = list(cases[0]["claims"])
        cases[1]["source_registry"] = list(cases[0]["source_registry"])
        baseline_cases = self._benchmark_cases("missing")
        baseline_cases.append({
            "case_id": "fixture-two",
            "draft": "Independent synthetic fixture.",
            "claims": [{"text": "Separate claim", "source_refs": ["missing"]}],
            "source_registry": [{"source_id": "known"}],
        })
        payload = {
            "baseline_cases": baseline_cases,
            "candidate_cases": cases,
            "reviewer": "reviewer",
        }
        run_staging_benchmark("worker_001", self.proposal["memory_id"], payload)
        dashboard = summarize_research_quality_dashboard("worker_001")
        self.assertGreaterEqual(dashboard["fixture_overlap_flagged_pair_total"], 1)
        self.assertEqual(dashboard["experiments"][0]["fixture_overlap_flagged_pair_count"],
                         dashboard["fixture_overlap_flagged_pair_total"])

    def test_research_quality_dashboard_rejects_invalid_limit(self):
        with self.assertRaisesRegex(ValueError, "limit"):
            summarize_research_quality_dashboard("worker_001", 0)


    def test_staging_history_and_dashboards_are_isolated_by_worker(self):
        review_improvement_proposal(
            "worker_001", self.proposal["memory_id"],
            "approved_for_staging", "reviewer",
        )
        run_staging_benchmark("worker_001", self.proposal["memory_id"], {
            "baseline_cases": self._benchmark_cases("missing"),
            "candidate_cases": self._benchmark_cases("known"),
            "reviewer": "reviewer",
        })

        self.assertEqual(list_staging_experiments("worker_001")["count"], 1)
        self.assertEqual(list_staging_experiments("worker_002")["count"], 0)
        self.assertEqual(summarize_staging_experiments("worker_002")["experiment_count"], 0)
        self.assertEqual(summarize_repeatability("worker_002")["groups_meeting_min_trials"], 0)
        self.assertEqual(summarize_staging_provenance("worker_002")["record_count"], 0)
        self.assertEqual(summarize_research_quality_dashboard("worker_002")["experiment_count"], 0)

        with self.assertRaisesRegex(ValueError, "proposal was not found for this worker"):
            create_staging_experiment(
                "worker_002", self.proposal["memory_id"], self._payload(),
            )


if __name__ == "__main__":
    unittest.main()
