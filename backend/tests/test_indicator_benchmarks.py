import unittest

from app.indicator_benchmarks import run_indicator_benchmarks
from app.indicators import rsi


class IndicatorBenchmarkTests(unittest.TestCase):
    def test_reference_benchmarks_pass(self):
        report = run_indicator_benchmarks()
        self.assertEqual(report["status"], "passed", report["cases"])
        self.assertEqual(report["passed"], report["total"])
        self.assertGreaterEqual(report["total"], 10)

    def test_flat_series_rsi_is_neutral_after_warmup(self):
        self.assertEqual(rsi([10.0, 10.0, 10.0, 10.0], 2), [None, 50.0, 50.0])

    def test_monotonic_decline_rsi_is_zero_after_warmup(self):
        self.assertEqual(rsi([4.0, 3.0, 2.0, 1.0], 2), [None, 0.0, 0.0])

    def test_monotonic_rise_rsi_is_one_hundred_after_warmup(self):
        self.assertEqual(rsi([1.0, 2.0, 3.0, 4.0], 2), [None, 100.0, 100.0])


if __name__ == "__main__":
    unittest.main()
