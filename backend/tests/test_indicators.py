import unittest
from app.indicators import sma,ema,returns,rsi,macd,bollinger,realized_volatility
class IndicatorTests(unittest.TestCase):
 def test_sma(self): self.assertEqual(sma([1,2,3,4],2),[1.0,1.5,2.5,3.5])
 def test_sma_avoids_overflow_for_large_finite_values(self): self.assertEqual(sma([1e308,1e308],2),[1e308,1e308])
 def test_ema(self): self.assertEqual(len(ema([1,2,3],2)),3)
 def test_returns(self): self.assertAlmostEqual(returns([100,110,99])[0],.1)
 def test_rsi(self): self.assertTrue(all(x is None or 0<=x<=100 for x in rsi(list(range(1,40)))))
 def test_macd(self): self.assertEqual(len(macd(list(range(1,40)))["histogram"]),39)
 def test_bollinger(self): self.assertEqual(len(bollinger(list(range(1,25)))["upper"]),24)
 def test_returns_reject_nonfinite_result(self):
  with self.assertRaisesRegex(ValueError, "return is non-finite"):
   returns([1e-308, 1e308])
 def test_indicators_reject_nonfinite_input(self):
  with self.assertRaisesRegex(ValueError, "finite numeric"):
   sma([1, float("nan"), 3], 2)
 def test_indicators_reject_unconvertible_large_integer(self):
  with self.assertRaisesRegex(ValueError, "finite numeric"):
   ema([10**10000, 2], 2)
 def test_volatility(self): self.assertGreater(realized_volatility([100,101,99,102])["per_observation"],0)
if __name__=="__main__": unittest.main()
