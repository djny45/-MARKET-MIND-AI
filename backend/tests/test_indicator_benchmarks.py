import unittest
from app.indicator_benchmarks import run_indicator_benchmarks

class IndicatorBenchmarkTests(unittest.TestCase):
    def test_reference_benchmarks_pass(self):
        report = run_indicator_benchmarks()
        self.assertEqual(report["status"], "passed", report["cases"])
        self.assertEqual(report["passed"], report["total"])
        self.assertGreaterEqual(report["total"], 6)

if __name__ == "__main__":
    unittest.main()
