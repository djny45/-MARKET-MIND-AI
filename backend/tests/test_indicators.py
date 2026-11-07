import unittest
from app.indicators import sma,ema,returns,rsi,macd,bollinger,realized_volatility
class IndicatorTests(unittest.TestCase):
 def test_sma(self): self.assertEqual(sma([1,2,3,4],2),[1.0,1.5,2.5,3.5])
 def test_sma_avoids_overflow_for_large_finite_values(self): self.assertEqual(sma([1e308,1e308],2),[1e308,1e308])
 def test_sma_handles_max_float_windows_without_overflow(self):
  value=float.fromhex("0x1.fffffffffffffp+1023")
  self.assertEqual(sma([value,value,value],3),[value,value,value])
  self.assertEqual(sma([-value,value],2),[-value,0.0])
 def test_bollinger_handles_large_finite_values(self):
  value=float.fromhex("0x1.fffffffffffffp+1023")
  result=bollinger([value,value,value],period=2)
  self.assertTrue(all(__import__("math").isfinite(x) for x in result["upper"]))
  self.assertEqual(result["upper"][-1],value)
 def test_realized_volatility_uses_scaled_variance(self):
  result=realized_volatility([1.0,1e308,1.0,1e308])
  self.assertTrue(__import__("math").isfinite(result["per_observation"]))
  self.assertGreater(result["per_observation"],1e307)
 def test_ema_avoids_intermediate_overflow(self):
  value=float.fromhex("0x1.fffffffffffffp+1023")
  result=ema([value,value,value],2)
  self.assertEqual(result,[value,value,value])
 def test_macd_rejects_overflowed_difference(self):
  value=float.fromhex("0x1.fffffffffffffp+1023")
  with self.assertRaisesRegex(ValueError,"MACD line must be finite"):
   macd([value,-value,value,-value],fast=2,slow=3,signal=2)
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
