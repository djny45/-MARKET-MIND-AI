import unittest
from app.instruments import search_instruments
class InstrumentSearchTests(unittest.TestCase):
 def test_symbol_search(self):
  result=search_instruments("AAPL")
  self.assertEqual(result["count"],1)
  self.assertEqual(result["instruments"][0]["symbol"],"AAPL")
  self.assertFalse(result["quotes_included"])
 def test_market_filter(self):
  result=search_instruments("",market="digital_assets")
  self.assertTrue(all(x["market"]=="digital_assets" for x in result["instruments"]))
 def test_name_search(self):
  result=search_instruments("Reliance")
  self.assertEqual(result["instruments"][0]["symbol"],"RELIANCE")
 def test_empty_query_limited(self):
  result=search_instruments("",limit=3)
  self.assertEqual(result["count"],3)
if __name__=="__main__": unittest.main()
