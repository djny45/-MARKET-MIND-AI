import unittest
from app.performance import max_drawdown, performance_metrics
class PerformanceTests(unittest.TestCase):
 def test_drawdown(self):
  self.assertAlmostEqual(max_drawdown([100,120,90,110]),-0.25)
 def test_flat_prices(self):
  result=performance_metrics([100,100,100,100],periods_per_year=252)
  self.assertEqual(result["cumulative_return"],0)
  self.assertIsNone(result["annualized_sharpe"])
 def test_benchmark_metrics(self):
  result=performance_metrics([100,102,101,104,106],[100,101,100,102,103],252)
  self.assertIsNotNone(result["beta"])
  self.assertIsNotNone(result["correlation_to_benchmark"])
 def test_invalid_prices(self):
  with self.assertRaises(ValueError): performance_metrics([100,0,101])
 def test_benchmark_length(self):
  with self.assertRaises(ValueError): performance_metrics([100,101,102],[100,101])
if __name__=="__main__": unittest.main()
