import unittest

from app.analytical_benchmarks import run_analytical_benchmarks


class AnalyticalBenchmarkTests(unittest.TestCase):
    def test_all_reference_vectors_pass(self):
        report = run_analytical_benchmarks()
        self.assertEqual(report["status"], "passed", report["cases"])
        self.assertEqual(report["case_count"], 11)
        self.assertEqual(report["failed_cases"], 0)

    def test_report_discloses_scope_and_limitations(self):
        report = run_analytical_benchmarks()
        self.assertEqual(report["scope"], "formula_and_reference_vector_correctness")
        self.assertTrue(report["research_only"])
        self.assertTrue(report["limitations"])


if __name__ == "__main__":
    unittest.main()
